#!/usr/bin/env python3
"""
Computer Control MCP - Core Implementation
==========================================
A full-featured MCP server that provides computer control capabilities:
- Mouse: move, click, double-click, right-click, drag, scroll
- Keyboard: type text, press keys, key combinations, hold/release
- Screen: screenshot (full screen / window / region), OCR text extraction
- Window: list windows, activate, get window info, get active window

Built on FastMCP with pyautogui, mss, and RapidOCR.
"""

import asyncio
import datetime
import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import mss
import numpy as np
import pyautogui
from mcp.server.fastmcp import FastMCP, Image
from PIL import Image as PILImage

# -- Window management --
try:
    import pywinctl as gw
except (NotImplementedError, ImportError):
    import pygetwindow as gw

# -- Fuzzy matching --
from fuzzywuzzy import fuzz, process

# -- OCR --
from rapidocr import RapidOCR

# -- Config --
DEBUG = os.getenv("COMPUTER_CONTROL_MCP_DEBUG", "").lower() in ("1", "true", "yes")
IS_DEVELOPMENT = os.getenv("ENV", "").lower() == "development"

# -- FastMCP instance --
mcp = FastMCP("ComputerControlMCP")

# -- OCR engine (lazy init) --
_ocr_engine: Optional[RapidOCR] = None


def _get_ocr_engine() -> RapidOCR:
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = RapidOCR()
    return _ocr_engine


# ============================================================
#  Logging
# ============================================================

def _log(message: str) -> None:
    """Log a message to stderr (MCP protocol uses stdout for JSON-RPC)."""
    try:
        msg = f"[ComputerControlMCP] {message}"
        print(msg, file=sys.stderr, flush=True)
    except Exception:
        pass


# ============================================================
#  Helpers
# ============================================================

def _get_downloads_dir() -> Path:
    """Resolve the default screenshot save directory."""
    custom = os.getenv("COMPUTER_CONTROL_MCP_SCREENSHOT_DIR")
    if custom:
        p = Path(custom)
        if p.is_dir():
            return p

    if os.name == "nt":
        import winreg
        sub_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        guid = "{374DE290-123F-4565-9164-39C4925E467B}"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
                return Path(winreg.QueryValueEx(key, guid)[0])
        except Exception:
            pass
    return Path.home() / "Downloads"


def _take_screenshot(region: Optional[Tuple[int, int, int, int]] = None) -> PILImage.Image:
    """Capture screen (or region) with mss, return PIL Image."""
    with mss.mss() as sct:
        if region is None:
            monitor = sct.monitors[0]
        else:
            left, top, width, height = region
            monitor = {"left": left, "top": top, "width": width, "height": height}
        raw = sct.grab(monitor)
        return PILImage.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def _save_image(image: Any, prefix: str = "screenshot", directory: Optional[Path] = None) -> Tuple[str, bytes]:
    """Save image to directory, return (filepath, bytes)."""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = str(uuid.uuid4())[:8]
    filename = f"{prefix}_{ts}_{uid}.png"
    target_dir = directory or _get_downloads_dir()
    filepath = target_dir / filename

    if hasattr(image, "save"):
        image.save(filepath)
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        img_bytes = buf.getvalue()
    elif hasattr(image, "data"):
        img_bytes = image.data
        filepath.write_bytes(img_bytes)
    else:
        raise TypeError(f"Unsupported image type: {type(image)}")

    return str(filepath.absolute()), img_bytes


def _get_windows() -> List[Dict[str, Any]]:
    """Return list of visible windows as dicts with title / window_obj."""
    result = []
    for w in gw.getAllWindows():
        if w.title:
            result.append({"title": w.title, "window_obj": w})
    return result


def _find_window(
    windows: List[Dict[str, Any]],
    title_pattern: Optional[str],
    use_regex: bool = False,
    threshold: int = 60,
) -> Optional[Dict[str, Any]]:
    """Find best-matching window from list."""
    if not title_pattern:
        return None

    if use_regex:
        pat = re.compile(title_pattern, re.IGNORECASE)
        for w in windows:
            if pat.search(w["title"]):
                return w
        return None

    titles = [w["title"] for w in windows]
    best, score = process.extractOne(title_pattern, titles, scorer=fuzz.partial_ratio)
    if score >= threshold:
        for w in windows:
            if w["title"] == best:
                return w
    return None


def _force_activate(window) -> None:
    """Bring a window to foreground (cross-platform best-effort)."""
    try:
        if os.name == "nt":
            import ctypes
            hwnd = window._hWnd
            if window.isMinimized:
                window.restore()
                time.sleep(0.1)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.BringWindowToTop(hwnd)
        window.activate()
        time.sleep(0.3)
    except Exception as e:
        _log(f"force_activate failed: {e}")


# ============================================================
#  MCP Tools -- Mouse
# ============================================================

@mcp.tool()
def move_mouse(x: int, y: int, duration: float = 0.3) -> str:
    """Move the mouse cursor to (x, y). Duration controls animation speed in seconds."""
    try:
        pyautogui.moveTo(x, y, duration=duration)
        return f"Moved mouse to ({x}, {y})"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def click(x: int, y: int, button: str = "left", clicks: int = 1) -> str:
    """Click at (x, y). Button: 'left' / 'right' / 'middle'. Clicks: 1 or 2 for double-click."""
    try:
        pyautogui.click(x, y, button=button, clicks=clicks)
        return f"Clicked {button} ({clicks}x) at ({x}, {y})"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def double_click(x: int, y: int, button: str = "left") -> str:
    """Double-click at (x, y)."""
    return click(x, y, button=button, clicks=2)


@mcp.tool()
def right_click(x: int, y: int) -> str:
    """Right-click at (x, y)."""
    return click(x, y, button="right", clicks=1)


@mcp.tool()
def mouse_down(button: str = "left") -> str:
    """Press and hold a mouse button ('left' / 'right' / 'middle'). Use mouse_up to release."""
    try:
        pyautogui.mouseDown(button=button)
        return f"Mouse {button} down"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def mouse_up(button: str = "left") -> str:
    """Release a held mouse button."""
    try:
        pyautogui.mouseUp(button=button)
        return f"Mouse {button} up"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def drag(
    from_x: int, from_y: int, to_x: int, to_y: int, button: str = "left", duration: float = 0.5
) -> str:
    """Drag from (from_x, from_y) to (to_x, to_y)."""
    try:
        pyautogui.moveTo(from_x, from_y)
        await asyncio.to_thread(pyautogui.drag, to_x - from_x, to_y - from_y, duration=duration, button=button)
        return f"Dragged from ({from_x}, {from_y}) to ({to_x}, {to_y})"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def scroll(amount: int, x: Optional[int] = None, y: Optional[int] = None) -> str:
    """Scroll the mouse wheel. Positive = up, negative = down. Optional (x, y) to move first."""
    try:
        if x is not None and y is not None:
            pyautogui.moveTo(x, y)
        pyautogui.scroll(amount)
        return f"Scrolled {amount} at ({x or 'current'}, {y or 'current'})"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def get_mouse_position() -> Dict[str, Any]:
    """Get the current mouse cursor position."""
    try:
        x, y = pyautogui.position()
        return {"x": x, "y": y}
    except Exception as e:
        return {"error": str(e)}


# ============================================================
#  MCP Tools -- Keyboard
# ============================================================

@mcp.tool()
def type_text(text: str, interval: float = 0.0) -> str:
    """Type text at the current cursor position. Interval controls delay between keystrokes."""
    try:
        pyautogui.typewrite(text, interval=interval)
        return f"Typed: {text}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def press_key(key: str) -> str:
    """
    Press and release a single key.
    Examples: 'enter', 'tab', 'escape', 'space', 'backspace', 'delete',
              'up', 'down', 'left', 'right', 'home', 'end',
              'f1'..'f12', 'win', 'winleft', 'winright',
              'ctrl', 'alt', 'shift', 'capslock'.
    """
    try:
        pyautogui.press(key)
        return f"Pressed: {key}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def hotkey(keys: str) -> str:
    """
    Press a key combination. Keys separated by '+'.
    Examples: 'ctrl+c', 'ctrl+v', 'alt+tab', 'win+r', 'ctrl+shift+esc'.
    """
    try:
        combo = [k.strip() for k in keys.split("+")]
        pyautogui.hotkey(*combo)
        return f"Hotkey: {keys}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def key_down(key: str) -> str:
    """Hold down a key. Use key_up to release."""
    try:
        pyautogui.keyDown(key)
        return f"Key down: {key}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def key_up(key: str) -> str:
    """Release a held key."""
    try:
        pyautogui.keyUp(key)
        return f"Key up: {key}"
    except Exception as e:
        return f"Error: {e}"


# ============================================================
#  MCP Tools -- Screen
# ============================================================

@mcp.tool()
def get_screen_size() -> Dict[str, Any]:
    """Get the primary screen resolution."""
    try:
        w, h = pyautogui.size()
        return {"width": w, "height": h}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def screenshot(
    title_pattern: Optional[str] = None,
    use_regex: bool = False,
    threshold: int = 60,
    save_to_downloads: bool = False,
) -> Image:
    """
    Take a screenshot of the entire screen or a specific window.

    Args:
        title_pattern: Window title to match. If None, captures the full screen.
        use_regex: Treat title_pattern as a regex.
        threshold: Fuzzy match threshold (0-100).
        save_to_downloads: Also save a copy to the downloads folder.

    Returns:
        MCP Image object of the screenshot.
    """
    try:
        window = None
        if title_pattern:
            windows = _get_windows()
            match = _find_window(windows, title_pattern, use_regex, threshold)
            window = match["window_obj"] if match else None

        if window is None:
            _log("Taking full-screen screenshot")
            img = _take_screenshot()
        else:
            _log(f"Capturing window: {window.title}")
            prev_active = gw.getActiveWindow()
            _force_activate(window)

            screen_w, screen_h = pyautogui.size()
            region = (
                max(window.left, 0),
                max(window.top, 0),
                min(window.width, screen_w),
                min(window.height, screen_h),
            )
            img = _take_screenshot(region)

            # Restore previous active window
            if prev_active and prev_active != window:
                try:
                    _force_activate(prev_active)
                except Exception:
                    pass

        tmp_dir = Path(tempfile.mkdtemp())
        filepath, _ = _save_image(img, "screenshot", tmp_dir)

        if save_to_downloads:
            shutil.copy(filepath, _get_downloads_dir())

        return Image(filepath)
    except Exception as e:
        _log(f"screenshot error: {e}\n{traceback.format_exc()}")
        return f"Error: {e}"


@mcp.tool()
def screenshot_with_ocr(
    title_pattern: Optional[str] = None,
    use_regex: bool = False,
    threshold: int = 60,
    scale_percent: int = 100,
) -> str:
    """
    Take a screenshot and extract text with coordinates using OCR.

    Returns JSON: [[[x1,y1],[x2,y2],[x3,y3],[x4,y4]], "text", confidence], ...

    The coordinates are relative to the captured region. Use them to click on text.

    Args:
        title_pattern: Window title to match. None = full screen.
        use_regex: Regex mode.
        threshold: Fuzzy match threshold (0-100).
        scale_percent: Downscale before OCR for speed (100 = no scaling).
    """
    try:
        window = None
        offset_x, offset_y = 0, 0
        if title_pattern:
            windows = _get_windows()
            match = _find_window(windows, title_pattern, use_regex, threshold)
            window = match["window_obj"] if match else None

        if window is None:
            _log("OCR: full screen")
            img = _take_screenshot()
        else:
            _log(f"OCR: window '{window.title}'")
            prev_active = gw.getActiveWindow()
            _force_activate(window)
            offset_x, offset_y = max(window.left, 0), max(window.top, 0)

            screen_w, screen_h = pyautogui.size()
            region = (
                offset_x, offset_y,
                min(window.width, screen_w), min(window.height, screen_h),
            )
            img = _take_screenshot(region)

            if prev_active and prev_active != window:
                try:
                    _force_activate(prev_active)
                except Exception:
                    pass

        tmp_dir = Path(tempfile.mkdtemp())
        filepath, _ = _save_image(img, "ocr_screenshot", tmp_dir)

        # Read with OpenCV
        import cv2
        cv_img = cv2.imread(filepath)
        if cv_img is None:
            return f"Error: Failed to read captured image from {filepath}"

        # Scale down for speed
        if scale_percent != 100:
            w = max(1, int(cv_img.shape[1] * scale_percent / 100))
            h = max(1, int(cv_img.shape[0] * scale_percent / 100))
            cv_img = cv2.resize(cv_img, (w, h), interpolation=cv2.INTER_AREA)
            scale_x = 100 / scale_percent
            scale_y = 100 / scale_percent
        else:
            scale_x = 1.0
            scale_y = 1.0

        engine = _get_ocr_engine()
        result = engine(cv_img)
        boxes, txts, scores = result.boxes, result.txts, result.scores

        items = []
        for box, text, score in zip(boxes, txts, scores):
            # Scale boxes back + add window offset
            scaled_box = box.tolist()
            for pt in scaled_box:
                pt[0] = int(pt[0] * scale_x + offset_x)
                pt[1] = int(pt[1] * scale_y + offset_y)
            items.append([scaled_box, text, float(score)])

        _log(f"OCR found {len(items)} text blocks")
        return json.dumps(items, ensure_ascii=False)
    except Exception as e:
        _log(f"OCR error: {e}\n{traceback.format_exc()}")
        return f"Error: {e}"


# ============================================================
#  MCP Tools -- Window Management
# ============================================================

@mcp.tool()
def list_windows() -> List[Dict[str, Any]]:
    """List all visible windows with their titles and positions."""
    result = []
    for w in gw.getAllWindows():
        if w.title:
            result.append({
                "title": w.title,
                "left": w.left,
                "top": w.top,
                "width": w.width,
                "height": w.height,
                "isMinimized": w.isMinimized,
                "isMaximized": w.isMaximized,
            })
    return result


@mcp.tool()
def get_active_window() -> Dict[str, Any]:
    """Get the currently active (foreground) window."""
    try:
        w = gw.getActiveWindow()
        if w is None:
            return {"error": "No active window"}
        return {
            "title": w.title,
            "left": w.left,
            "top": w.top,
            "width": w.width,
            "height": w.height,
            "isMinimized": w.isMinimized,
            "isMaximized": w.isMaximized,
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def activate_window(
    title_pattern: str,
    use_regex: bool = False,
    threshold: int = 60,
) -> str:
    """
    Bring a window to the foreground by its title.

    Args:
        title_pattern: Window title (or part of it).
        use_regex: Treat pattern as regex.
        threshold: Fuzzy match threshold (0-100).
    """
    try:
        windows = _get_windows()
        match = _find_window(windows, title_pattern, use_regex, threshold)
        if match is None:
            return f"No window matched '{title_pattern}'"

        w = match["window_obj"]
        _force_activate(w)
        return f"Activated window: {w.title}"
    except Exception as e:
        return f"Error: {e}"


# ============================================================
#  MCP Tools -- Utility
# ============================================================

@mcp.tool()
def wait(milliseconds: int) -> str:
    """Wait for a specified number of milliseconds."""
    time.sleep(milliseconds / 1000.0)
    return f"Waited {milliseconds}ms"


@mcp.tool()
def get_clipboard() -> str:
    """Get current clipboard text content."""
    try:
        import pyperclip
        return pyperclip.paste()
    except ImportError:
        return "Error: pyperclip not installed. Run: pip install pyperclip"


@mcp.tool()
def set_clipboard(text: str) -> str:
    """Set clipboard text content."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return "Clipboard set"
    except ImportError:
        return "Error: pyperclip not installed. Run: pip install pyperclip"


# ============================================================
#  Entry point
# ============================================================

def main():
    """Run the MCP server."""
    _log(f"Computer Control MCP v{__import__('computer_control_mcp').__version__}")
    mcp.run()


if __name__ == "__main__":
    main()
