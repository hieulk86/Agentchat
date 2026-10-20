"""Chạy server: python -m agentchat [--host 0.0.0.0] [--port 8000]"""

import argparse

import uvicorn

parser = argparse.ArgumentParser(description="Chạy giao diện web AgentChat")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=8000)
parser.add_argument("--reload", action="store_true", help="tự khởi động lại khi sửa code")
args = parser.parse_args()

uvicorn.run("agentchat.server:create_app", factory=True, host=args.host, port=args.port, reload=args.reload)
