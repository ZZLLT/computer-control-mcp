"""Push all files to GitHub via the Contents API."""
import base64, json, os, sys, urllib.request

TOKEN = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_TOKEN", "")
OWNER = "ZZLLT"
REPO = "computer-control-mcp"
BRANCH = "main"
BASE = r"D:\OH-WorkSpace\computer-control-mcp"
MSG = "Initial commit: Computer Control MCP Server"

def push_file(path, content, message=MSG):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}"
    encoded = base64.b64encode(content if isinstance(content, bytes) else content.encode()).decode()
    data = json.dumps({
        "message": message,
        "content": encoded,
        "branch": BRANCH,
    }).encode()
    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return True, result.get("content", {}).get("path", "")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode()[:300]}"
    except Exception as e:
        return False, str(e)

files = []
for root, dirs, fnames in os.walk(BASE):
    dirs[:] = [d for d in dirs if d != ".git"]
    for fname in fnames:
        full = os.path.join(root, fname)
        rel = os.path.relpath(full, BASE).replace("\\", "/")
        files.append((rel, full))

files.sort()
print(f"Pushing {len(files)} files to {OWNER}/{REPO}...")

for rel, full in files:
    with open(full, "rb") as f:
        content = f.read()
    ok, info = push_file(rel, content, MSG)
    status = "OK" if ok else f"FAIL: {info}"
    print(f"  [{status}] {rel}")

print("\nDone!")
