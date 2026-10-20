"""Phòng chat: giữ lịch sử chung và điều phối lượt nói giữa các agent."""

from __future__ import annotations

import asyncio
import itertools
import logging
from typing import Awaitable, Callable

from .config import RoomConfig
from .llm import Backend

log = logging.getLogger(__name__)

USER = "Người dùng"
Broadcast = Callable[[dict], Awaitable[None]]


class Room:
    def __init__(self, config: RoomConfig, backend: Backend, broadcast: Broadcast):
        self.config = config
        self.backend = backend
        self.broadcast = broadcast
        self.messages: list[dict] = []
        self._ids = itertools.count(1)
        self._task: asyncio.Task | None = None
        self._rr_index = 0

    # ---------- trạng thái ----------

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def snapshot(self) -> dict:
        s = self.config.settings
        return {
            "type": "state",
            "running": self.running,
            "messages": self.messages,
            "agents": [a.to_dict() for a in self.config.agents],
            "settings": {"mode": s.mode, "max_turns": s.max_turns, "stop_token": s.stop_token},
        }

    def _agent(self, name: str):
        return next(a for a in self.config.agents if a.name == name)

    async def _add(self, kind: str, speaker: str, content: str) -> dict:
        msg = {"id": next(self._ids), "kind": kind, "speaker": speaker, "content": content}
        self.messages.append(msg)
        await self.broadcast({"type": "message", "message": msg})
        return msg

    # ---------- điều khiển từ giao diện ----------

    async def post_user(self, text: str, mode: str | None = None, max_turns: int | None = None) -> None:
        """Người dùng gửi tin. Nếu phòng đang rảnh thì bắt đầu một lượt chạy mới."""
        await self._add("user", USER, text)
        if mode in ("round_robin", "moderator"):
            self.config.settings.mode = mode
        if max_turns:
            self.config.settings.max_turns = max(1, min(int(max_turns), 50))
        if not self.running:
            self._task = asyncio.create_task(self._run())
            await self.broadcast({"type": "status", "running": True})

    async def stop(self) -> None:
        if self.running:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def reset(self) -> None:
        await self.stop()
        self.messages.clear()
        self._rr_index = 0
        await self.broadcast(self.snapshot())

    # ---------- vòng điều phối ----------

    async def _run(self) -> None:
        settings = self.config.settings
        try:
            for _ in range(settings.max_turns):
                speaker = await self._pick_next()
                text = await self._speak(speaker)
                if settings.stop_token in text:
                    await self._add("system", "Hệ thống", f"{speaker} đã kết thúc nhiệm vụ.")
                    break
            else:
                await self._add("system", "Hệ thống", f"Đã đạt giới hạn {settings.max_turns} lượt.")
        except asyncio.CancelledError:
            await self._add("system", "Hệ thống", "Đã dừng theo yêu cầu.")
            raise
        except Exception as exc:  # báo lỗi lên giao diện thay vì im lặng
            log.exception("room run failed")
            await self._add("system", "Hệ thống", f"Lỗi: {exc}")
        finally:
            await self.broadcast({"type": "status", "running": False})

    async def _pick_next(self) -> str:
        agents = self.config.agents
        if self.config.settings.mode == "round_robin" or len(agents) == 1:
            name = agents[self._rr_index % len(agents)].name
            self._rr_index += 1
            return name

        names = [a.name for a in agents]
        prompt = (
            self._roster()
            + "\n\nLịch sử hội thoại:\n"
            + self._transcript()
            + "\n\nAi nên nói tiếp? Tránh chọn lại người vừa nói nếu không thật cần thiết."
        )
        name, reason = await self.backend.choose_next(self.config.settings.moderator_model, prompt, names)
        if name not in names:
            name = names[0]
        await self._add("system", "Điều phối viên", f"Mời {name}: {reason}")
        return name

    async def _speak(self, name: str) -> str:
        agent = self._agent(name)
        msg = {"id": next(self._ids), "kind": "agent", "speaker": name, "content": ""}
        self.messages.append(msg)
        await self.broadcast({"type": "agent_start", "message": msg})
        try:
            async for chunk in self.backend.stream_reply(agent, self._system_for(name), self._prompt_for(name)):
                msg["content"] += chunk
                await self.broadcast({"type": "delta", "id": msg["id"], "text": chunk})
        finally:
            await self.broadcast({"type": "agent_end", "id": msg["id"]})
        return msg["content"]

    # ---------- dựng prompt ----------

    def _roster(self) -> str:
        lines = ["Thành viên trong phòng:"]
        for a in self.config.agents:
            first_line = a.system.strip().splitlines()[0] if a.system.strip() else ""
            lines.append(f"- {a.name}: {first_line}")
        return "\n".join(lines)

    def _transcript(self) -> str:
        return "\n\n".join(
            f"[{m['speaker']}]: {m['content']}" for m in self.messages if m["kind"] in ("user", "agent")
        )

    def _system_for(self, name: str) -> str:
        agent = self._agent(name)
        return (
            agent.system.strip()
            + "\n\nBạn đang ở trong một phòng chat nhóm cùng người dùng và các agent khác.\n"
            + self._roster()
            + "\n\nQuy tắc: chỉ nói với tư cách của bạn, không viết thay người khác, không lặp lại "
            "nội dung đã có, trả lời bằng ngôn ngữ của người dùng. Khi toàn bộ nhiệm vụ đã hoàn "
            f"thành, kết thúc tin nhắn bằng {self.config.settings.stop_token}."
        )

    def _prompt_for(self, name: str) -> str:
        return f"Lịch sử hội thoại:\n\n{self._transcript()}\n\nĐến lượt bạn ({name})."
