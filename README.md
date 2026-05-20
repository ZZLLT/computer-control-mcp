# Computer Control MCP 🖥️

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-purple)](https://modelcontextprotocol.io/)

一个全功能的 **MCP (Model Context Protocol)** 服务器，让 AI 助手能够直接操控你的电脑：鼠标、键盘、截图、OCR 文字识别、窗口管理。

A full-featured **MCP server** that gives AI assistants direct control over your computer: mouse, keyboard, screenshots, OCR, and window management.

---

## 功能 / Features

| 类别 Category | 工具 Tools |
|---|---|
| **🖱️ 鼠标 Mouse** | `move_mouse` `click` `double_click` `right_click` `drag` `scroll` `mouse_down` `mouse_up` `get_mouse_position` |
| **⌨️ 键盘 Keyboard** | `type_text` `press_key` `hotkey` `key_down` `key_up` |
| **📸 截图 Screen** | `screenshot` `screenshot_with_ocr` `get_screen_size` |
| **🪟 窗口 Window** | `list_windows` `get_active_window` `activate_window` |
| **🔧 工具 Utility** | `wait` `get_clipboard` `set_clipboard` |

### 亮点 / Highlights

- **OCR 文字识别** — 截图并提取文字 + 坐标，AI 可以"看到"屏幕上的文字然后精准点击
- **热键支持** — `ctrl+c`、`win+r`、`alt+tab` 等组合键全面支持
- **窗口管理** — 模糊搜索窗口标题，自动激活
- **跨平台** — Windows / macOS / Linux，功能完整
- **FastMCP 构建** — 使用官方 MCP Python SDK，稳定可靠

---

## 快速开始 / Quick Start

### 安装 / Install

```bash
# 使用 uvx (推荐)
uvx computer-control-mcp@latest

# 或全局安装
pip install computer-control-mcp
```

### Claude Desktop 配置

在 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "computer-control-mcp": {
      "command": "uvx",
      "args": ["computer-control-mcp@latest"]
    }
  }
}
```

### 环境变量 / Environment Variables

| 变量 | 说明 | 默认值 |
|---|---|---|
| `COMPUTER_CONTROL_MCP_SCREENSHOT_DIR` | 截图保存目录 | 系统下载文件夹 |
| `COMPUTER_CONTROL_MCP_DEBUG` | 开启调试日志 (`1` / `true`) | 关闭 |

---

## 使用示例 / Usage Examples

### 截图 + OCR 识别

```
AI: 打开记事本，输入一些文字

1. activate_window("记事本")          # 激活窗口
2. type_text("Hello World")            # 输入文字
3. screenshot_with_ocr()               # 截图并识别文字
   → [坐标, "Hello World", 0.99]      # 返回文字位置和置信度
4. click(x, y)                         # 点击文字位置
```

### 组合键操作

```
AI: 打开运行对话框

1. hotkey("win+r")                     # Win + R
2. type_text("notepad")                # 输入 notepad
3. press_key("enter")                  # 回车
```

### 拖拽操作

```
AI: 把文件拖到文件夹

1. drag(from_x, from_y, to_x, to_y)   # 拖拽文件
```

---

## 开发 / Development

```bash
git clone https://github.com/ZZLLT/computer-control-mcp.git
cd computer-control-mcp

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 直接运行
python -m computer_control_mcp
```

---

## 技术栈 / Tech Stack

- **[FastMCP](https://github.com/jlowin/fastmcp)** — MCP server 框架
- **[PyAutoGUI](https://pyautogui.readthedocs.io/)** — 鼠标键盘模拟
- **[MSS](https://github.com/BoboTiG/python-mss)** — 高性能截图
- **[RapidOCR](https://github.com/RapidAI/RapidOCR)** — 轻量级 OCR
- **[pywinctl](https://github.com/Kalmat/PyWinCtl)** — 跨平台窗口管理

---

## 同类项目 / Similar Projects

- [AB498/computer-control-mcp](https://github.com/AB498/computer-control-mcp) — 灵感来源
- [anthropics/anthropic-quickstarts](https://github.com/anthropics/anthropic-quickstarts) — Anthropic 官方 computer-use demo

---

## License

MIT © 2026 ZZLLT
