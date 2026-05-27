import pytest

from app.events import ModuleChatEvent


def test_module_chat_event_has_required_fields():
    ev = ModuleChatEvent(
        seq=1,
        module_id="sticky-1",
        text="hi all",
        at=1.0,
        actor_id="p",
        actor_username="alex",
        actor_kind="human",
    )
    assert ev.type == "module_chat"
    assert ev.module_id == "sticky-1"
    assert ev.text == "hi all"


from app.events import Participant
from app.models import (
    DrawBoardModule,
    Music,
    PartyConfig,
    Room,
    Theme,
    WorldSize,
)
from app.world import PartyWorld


def _world() -> PartyWorld:
    party = PartyConfig(
        slug="t",
        name="t",
        description="t",
        theme=Theme(floor="#fff", accent="#000"),
        zones=[],
        music=Music(url=None, label="x"),
        worldSize=WorldSize(width=800, height=500),
        room=Room(border="1px solid #000", walls=[]),
        modules=[DrawBoardModule(id="draw-1", x=0, y=0, w=180, h=80)],
    )
    return PartyWorld(party)


def _participant(world: PartyWorld, pid: str, x: float, y: float) -> None:
    world.join(
        Participant(
            id=pid, kind="human", username=pid, color="#ff6b9d",
            x=x, y=y, joined_at=0.0,
        )
    )


def test_module_chat_history_returns_last_50_for_module():
    world = _world()
    _participant(world, "p1", x=50.0, y=50.0)  # inside draw-1 rect
    for i in range(60):
        world.module_chat("p1", "draw-1", f"msg{i:02d}")
    hist = world.module_chat_history("draw-1")
    assert len(hist) == 50
    assert hist[0]["text"] == "msg10"
    assert hist[-1]["text"] == "msg59"


def test_module_chat_history_isolated_per_module():
    world = _world()
    _participant(world, "p1", x=50.0, y=50.0)
    world.module_chat("p1", "draw-1", "hello")
    assert world.module_chat_history("draw-1")[0]["text"] == "hello"
    assert world.module_chat_history("other") == []
