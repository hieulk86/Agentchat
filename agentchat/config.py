"""Đọc cấu hình agent từ file YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_MODEL = "claude-opus-5-5"


@dataclass
class AgentConfig:
    name: str
    system: str
    model: str = DEFAULT_MODEL
    effort: str = "medium"
    color: str = "#64748b"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "system": self.system,
            "model": self.model,
            "effort": self.effort,
            "color": self.color,
        }


@dataclass
class Settings:
    mode: str = "moderator"  # "round_robin" hoặc "moderator"
    max_turns: int = 8
    moderator_model: str = DEFAULT_MODEL
    stop_token: str = "[DONE]"


@dataclass
class RoomConfig:
    agents: list[AgentConfig]
    settings: Settings = field(default_factory=Settings)


def load_config(path: str | Path) -> RoomConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    agents = [AgentConfig(**a) for a in data.get("agents", [])]
    if not agents:
        raise ValueError(f"{path}: cần ít nhất một agent")
    names = [a.name for a in agents]
    if len(set(names)) != len(names):
        raise ValueError(f"{path}: tên agent bị trùng")
    settings = Settings(**data.get("settings", {}))
    if settings.mode not in ("round_robin", "moderator"):
        raise ValueError(f"{path}: mode phải là round_robin hoặc moderator")
    return RoomConfig(agents=agents, settings=settings)
