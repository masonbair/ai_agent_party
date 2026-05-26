from app.parties_data import PARTY_REGISTRY


def test_cream_terrazzo_has_default_modules() -> None:
    party = PARTY_REGISTRY["cream-terrazzo"]
    kinds = [m.kind for m in party.modules]
    assert "lighting" in kinds
    assert "stickynotes" in kinds
    assert "drawboard" in kinds
    sticky = next(m for m in party.modules if m.kind == "stickynotes")
    assert sticky.id == "sticky-1"
    draw = next(m for m in party.modules if m.kind == "drawboard")
    assert draw.id == "draw-1"
