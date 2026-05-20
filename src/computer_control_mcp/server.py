"""
Standalone server entry point for Computer Control MCP.

Usage:
    python -m computer_control_mcp.server
    # or via console_scripts entry point
"""

from computer_control_mcp.core import main as run_server


def main():
    print("Starting Computer Control MCP server...", flush=True)
    run_server()


if __name__ == "__main__":
    main()
