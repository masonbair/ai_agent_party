from app.models import Music, PartyConfig, Room, Theme, Wall, WorldSize, Zone

CREAM_TERRAZZO = PartyConfig(
    slug="cream-terrazzo",
    name="Cream Terrazzo Lounge",
    description="A bright, friendly room with bold pastel zones.",
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
            x=6.0,
            y=8.0,
            width=34.0,
            height=36.0,
            color="#ff6b9d",
            labelColor="#ffffff",
            borderColor="#8b1a4a",
        ),
        Zone(
            id="chill",
            label="CHILL",
            x=60.0,
            y=8.0,
            width=34.0,
            height=28.0,
            color="#4dd0e1",
            labelColor="#ffffff",
            borderColor="#00606e",
        ),
        Zone(
            id="snacks",
            label="SNACKS",
            x=28.0,
            y=58.0,
            width=44.0,
            height=34.0,
            color="#ffb74d",
            labelColor="#ffffff",
            borderColor="#6b3a00",
        ),
    ],
    music=Music(url=None, label="Music coming soon"),
    worldSize=WorldSize(width=800, height=500),
    room=Room(
        clipPath=None,
        border="6px solid #8b6f47",
        borderRadius=12,
        walls=[
            # Vertical stub between dance and chill, top half.
            Wall(x=50.0, y=0.0, width=0.75, height=30.0, color="#8b6f47"),
            # Horizontal stub on the right above snacks.
            Wall(x=75.0, y=40.0, width=25.0, height=1.2, color="#8b6f47"),
        ],
    ),
)

PARTY_REGISTRY: dict[str, PartyConfig] = {CREAM_TERRAZZO.slug: CREAM_TERRAZZO}
