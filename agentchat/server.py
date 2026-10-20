"""Server web: FastAPI + WebSocket để xem và điều khiển phòng chat."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import load_config
from .llm import ClaudeBackend, MockBackend
from .room import Room

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"

logging.basicConfig(level=logging.INFO)


def create_app(config_path: str | Path | None = None, backend=None) -> FastAPI:
    config = load_config(config_path or os.environ.get("AGENTCHAT_CONFIG", ROOT / "agents.yaml"))
    if backend is None:
        if os.environ.get("AGENTCHAT_MOCK") == "1":
            backend = MockBackend(stop_token=config.settings.stop_token)
        else:
            backend = ClaudeBackend()

    clients: set[WebSocket] = set()

    async def broadcast(event: dict) -> None:
        for ws in list(clients):
            try:
                await ws.send_json(event)
            except Exception:
                clients.discard(ws)

    room = Room(config, backend, broadcast)
    app = FastAPI(title="AgentChat")
    app.state.room = room

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html")

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        clients.add(ws)
        await ws.send_json(room.snapshot())
        try:
            while True:
                data = await ws.receive_json()
                action = data.get("action")
                if action == "send" and str(data.get("text", "")).strip():
                    await room.post_user(data["text"].strip(), data.get("mode"), data.get("max_turns"))
                elif action == "stop":
                    await room.stop()
                elif action == "reset":
                    await room.reset()
        except WebSocketDisconnect:
            clients.discard(ws)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
