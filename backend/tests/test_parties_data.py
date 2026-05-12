from app.parties_data import CREAM_TERRAZZO


def test_cream_terrazzo_has_expected_slug_and_zones() -> None:
    assert CREAM_TERRAZZO.slug == "cream-terrazzo"
    zone_ids = {z.id for z in CREAM_TERRAZZO.zones}
    assert zone_ids == {"dance", "chill", "snacks"}


def test_cream_terrazzo_music_is_placeholder() -> None:
    assert CREAM_TERRAZZO.music.url is None
    assert "coming soon" in CREAM_TERRAZZO.music.label.lower()
