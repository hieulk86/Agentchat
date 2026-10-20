import asyncio

from fastapi.testclient import TestClient

from agentchat.config import AgentConfig, RoomConfig, Settings, load_config
from agentchat.llm import MockBackend
from agentchat.room import Room
from agentchat.server import create_app


def make_room(mode="round_robin", max_turns=5, done_after=99):
    config = RoomConfig(
        agents=[AgentConfig(name="A", system="Agent A"), AgentConfig(name="B", system="Agent B")],
        settings=Settings(mode=mode, max_turns=max_turns),
    )
    events = []

    async def broadcast(ev):
        events.append(ev)

    return Room(config, MockBackend(delay=0, done_after=done_after), broadcast), events


async def run_until_idle(room):
    await asyncio.sleep(0)
    while room.running:
        await asyncio.sleep(0.01)


def test_round_robin_alternates_and_respects_max_turns():
    async def main():
        room, _ = make_room(max_turns=4)
        await room.post_user("xin chào")
        await run_until_idle(room)
        speakers = [m["speaker"] for m in room.messages if m["kind"] == "agent"]
        assert speakers == ["A", "B", "A", "B"]
        assert "giới hạn" in room.messages[-1]["content"]

    asyncio.run(main())


def test_stop_token_ends_conversation():
    async def main():
        room, _ = make_room(max_turns=10, done_after=2)
        await room.post_user("làm việc đi")
        await run_until_idle(room)
        assert len([m for m in room.messages if m["kind"] == "agent"]) == 2
        assert "kết thúc" in room.messages[-1]["content"]

    asyncio.run(main())


def test_moderator_mode_announces_choice():
    async def main():
        room, _ = make_room(mode="moderator", max_turns=2)
        await room.post_user("hi")
        await run_until_idle(room)
        notes = [m for m in room.messages if m["speaker"] == "Điều phối viên"]
        assert len(notes) == 2

    asyncio.run(main())


def test_stop_cancels_run():
    async def main():
        config = RoomConfig(agents=[AgentConfig(name="A", system="x")], settings=Settings(max_turns=50))
        room = Room(config, MockBackend(delay=0.01, done_after=999), lambda ev: asyncio.sleep(0))
        await room.post_user("chạy mãi")
        await asyncio.sleep(0.1)
        await room.stop()
        assert not room.running
        assert room.messages[-1]["content"] == "Đã dừng theo yêu cầu."

    asyncio.run(main())


def test_default_config_loads():
    config = load_config("agents.yaml")
    assert [a.name for a in config.agents] == ["Planner", "Coder", "Reviewer"]


def test_websocket_flow():
    app = create_app(backend=MockBackend(delay=0, done_after=2))
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        state = ws.receive_json()
        assert state["type"] == "state" and len(state["agents"]) == 3
        ws.send_json({"action": "send", "text": "xin chào", "mode": "round_robin", "max_turns": 3})
        seen = []
        while True:
            ev = ws.receive_json()
            seen.append(ev["type"])
            if ev["type"] == "status" and not ev["running"]:
                break
        assert seen.count("agent_start") == 2
        assert "delta" in seen
        assert client.get("/").status_code == 200
