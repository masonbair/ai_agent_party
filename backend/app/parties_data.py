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

SPEAKEASY = PartyConfig(
    slug="speakeasy",
    name="The Speakeasy",
    description="A warm prohibition-era bar with low light, a long polished counter, and intimate booths.",
    theme=Theme(
        floor="linear-gradient(180deg, #4a3526 0%, #3a2516 100%)",
        accent="#c89b6a",
    ),
    zones=[
        Zone(
            id="bar",
            label="BAR",
            x=10.0,
            y=28.0,
            width=80.0,
            height=18.0,
            color="#d4a574",
            labelColor="#3a2516",
            borderColor="#6b4a2a",
        ),
        Zone(
            id="dance",
            label="DANCE",
            x=8.0,
            y=52.0,
            width=40.0,
            height=40.0,
            color="#b8336a",
            labelColor="#ffffff",
            borderColor="#5a1a35",
        ),
        Zone(
            id="booths",
            label="BOOTHS",
            x=52.0,
            y=52.0,
            width=40.0,
            height=40.0,
            color="#7a5836",
            labelColor="#ffffff",
            borderColor="#3d2c1c",
        ),
    ],
    music=Music(url=None, label="Music coming soon"),
    worldSize=WorldSize(width=800, height=500),
    room=Room(
        clipPath=None,
        border="8px solid #8a6234",
        borderRadius=8,
        walls=[
            # Left counter segment
            Wall(x=15.0, y=22.0, width=30.0, height=1.5, color="#c89b6a"),
            # Right counter segment (gap in the middle for walking through)
            Wall(x=55.0, y=22.0, width=30.0, height=1.5, color="#c89b6a"),
        ],
    ),
)

PARTY_REGISTRY: dict[str, PartyConfig] = {CREAM_TERRAZZO.slug: CREAM_TERRAZZO, SPEAKEASY.slug: SPEAKEASY}
