from app.models import Music, PartyConfig, Theme, WorldSize, Zone

CREAM_TERRAZZO = PartyConfig(
    slug="cream-terrazzo",
    name="Cream Terrazzo Lounge",
    description="A bright, friendly room with soft pastel zones.",
    theme=Theme(
        floor=(
            "#f4ead5 radial-gradient(circle 2px at 10% 20%, #c0a070 1px, transparent 2px), "
            "radial-gradient(circle 2px at 40% 60%, #a85d3a 1px, transparent 2px), "
            "radial-gradient(circle 2px at 70% 30%, #c0a070 1px, transparent 2px), "
            "radial-gradient(circle 2px at 85% 80%, #8b6f47 1px, transparent 2px), "
            "radial-gradient(circle 2px at 25% 85%, #c0a070 1px, transparent 2px)"
        ),
        accent="#ff6b9d",
    ),
    zones=[
        Zone(
            id="dance",
            label="DANCE",
            x=25.0,
            y=24.0,
            width=40.0,
            height=36.0,
            color="rgba(255,107,157,0.25)",
            labelColor="#8b1a4a",
        ),
        Zone(
            id="chill",
            label="CHILL",
            x=75.0,
            y=24.0,
            width=40.0,
            height=36.0,
            color="rgba(77,208,225,0.25)",
            labelColor="#00606e",
        ),
        Zone(
            id="snacks",
            label="SNACKS",
            x=50.0,
            y=76.0,
            width=40.0,
            height=36.0,
            color="rgba(255,167,38,0.30)",
            labelColor="#6b3a00",
        ),
    ],
    music=Music(url=None, label="Music coming soon"),
    worldSize=WorldSize(width=800, height=500),
)

PARTY_REGISTRY: dict[str, PartyConfig] = {CREAM_TERRAZZO.slug: CREAM_TERRAZZO}
