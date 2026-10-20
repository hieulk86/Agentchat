"""Lớp gọi model: Claude thật (Anthropic SDK) hoặc bản giả lập để chạy thử."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, Protocol

import anthropic

from .config import AgentConfig

# Các model hỗ trợ `fallbacks: "default"` (tự chuyển model khi bị từ chối vì chính sách).
FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class Backend(Protocol):
    def stream_reply(self, agent: AgentConfig, system: str, prompt: str) -> AsyncIterator[str]: ...

    async def choose_next(self, model: str, prompt: str, names: list[str]) -> tuple[str, str]: ...


def _fallback_kwargs(model: str) -> dict:
    if model in FALLBACK_MODELS:
        return {"betas": [FALLBACK_BETA], "fallbacks": "default"}
    return {}


class ClaudeBackend:
    def __init__(self, client: anthropic.AsyncAnthropic | None = None):
        self.client = client or anthropic.AsyncAnthropic()

    async def stream_reply(self, agent: AgentConfig, system: str, prompt: str) -> AsyncIterator[str]:
        async with self.client.beta.messages.stream(
            model=agent.model,
            max_tokens=64000,
            system=system,
            thinking={"type": "adaptive"},
            output_config={"effort": agent.effort},
            messages=[{"role": "user", "content": prompt}],
            **_fallback_kwargs(agent.model),
        ) as stream:
            async for text in stream.text_stream:
                yield text
            final = await stream.get_final_message()
        if final.stop_reason == "refusal":
            yield "\n\n_(Model đã từ chối trả lời yêu cầu này.)_"
        elif final.stop_reason == "max_tokens":
            yield "\n\n_(Câu trả lời bị cắt do vượt giới hạn token.)_"

    async def choose_next(self, model: str, prompt: str, names: list[str]) -> tuple[str, str]:
        schema = {
            "type": "object",
            "properties": {
                "next": {"type": "string", "enum": names},
                "reason": {"type": "string"},
            },
            "required": ["next", "reason"],
            "additionalProperties": False,
        }
        response = await self.client.beta.messages.create(
            model=model,
            max_tokens=16000,
            system=(
                "Bạn là điều phối viên của một nhóm agent. Đọc cuộc hội thoại và chọn "
                "thành viên phù hợp nhất để nói tiếp. Lý do viết ngắn gọn bằng tiếng Việt."
            ),
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": prompt}],
            **_fallback_kwargs(model),
        )
        if response.stop_reason == "refusal":
            return names[0], "điều phối viên từ chối, chọn mặc định"
        text = next(b.text for b in response.content if b.type == "text")
        data = json.loads(text)
        return data["next"], data["reason"]


class MockBackend:
    """Trả lời giả để thử giao diện mà không tốn token (AGENTCHAT_MOCK=1)."""

    def __init__(self, delay: float = 0.03, stop_token: str = "[DONE]", done_after: int = 3):
        self.delay = delay
        self.stop_token = stop_token
        self.done_after = done_after
        self.calls = 0

    async def stream_reply(self, agent: AgentConfig, system: str, prompt: str) -> AsyncIterator[str]:
        self.calls += 1
        text = (
            f"Xin chào, mình là {agent.name}. Đây là câu trả lời giả lập số {self.calls} "
            f"(model {agent.model})."
        )
        if self.calls >= self.done_after:
            text += f" Mọi thứ ổn rồi. {self.stop_token}"
        for word in text.split(" "):
            await asyncio.sleep(self.delay)
            yield word + " "

    async def choose_next(self, model: str, prompt: str, names: list[str]) -> tuple[str, str]:
        await asyncio.sleep(self.delay)
        return names[self.calls % len(names)], "luân phiên (chế độ giả lập)"
