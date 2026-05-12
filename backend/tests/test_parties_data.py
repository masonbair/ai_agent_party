from app.parties_data import CREAM_TERRAZZO


def test_cream_terrazzo_has_expected_slug_and_zones() -> None:
    assert CREAM_TERRAZZO.slug == "cream-terrazzo"
    zone_ids = {z.id for z in CREAM_TERRAZZO.zones}
    assert zone_ids == {"dance", "chill", "snacks"}


def test_cream_terrazzo_music_is_placeholder() -> None:
    assert CREAM_TERRAZZO.music.url is None
    assert "coming soon" in CREAM_TERRAZZO.music.label.lower()


def test_cream_terrazzo_room_has_walls_and_border() -> None:
    room = CREAM_TERRAZZO.room
    assert room.border.startswith("6px")
    assert room.borderRadius == 12
    assert len(room.walls) == 2
    assert room.clipPath is None


def test_cream_terrazzo_zones_have_solid_fill_colors() -> None:
    # Filled boxes use a solid color (hex or rgb), not rgba with alpha.
    for z in CREAM_TERRAZZO.zones:
        assert z.color.startswith("#"), f"zone {z.id} should use solid hex fill"
        assert z.borderColor.startswith("#")
