"""Scout 入口点。"""

from .server import run


def main() -> None:
    """启动 Scout MCP 服务器。"""
    run()


if __name__ == "__main__":
    main()
