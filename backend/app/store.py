import uuid

from app.events import Agent
from app.models import PartyConfig, User
from app.parties_data import PARTY_REGISTRY
from app.dm_store import DmStore
from app.inbox import InboxHub
from app.realtime import PartyWorldHub
from app.session_presence import SessionPresenceHub
from app.world import PartyWorld


class Store:
    def __init__(self) -> None:
        self._sessions: dict[str, User] = {}
        self._parties: dict[str, PartyConfig] = dict(PARTY_REGISTRY)
        self._agents: dict[str, Agent] = {}
        self._worlds: dict[str, PartyWorld] = {}
        self._hubs: dict[str, PartyWorldHub] = {}
        self._session_presence: SessionPresenceHub | None = None
        self.dm_store: DmStore = DmStore()
        self.inbox_hub: InboxHub = InboxHub()

    def create_session(self, username: str, color: str) -> User:
        session_id = uuid.uuid4().hex
        user = User(session_id=session_id, username=username, color=color)
        self._sessions[session_id] = user
        return user

    def get_session(self, session_id: str) -> User | None:
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def worlds(self) -> list[PartyWorld]:
        return list(self._worlds.values())

    @property
    def session_presence(self) -> SessionPresenceHub:
        if self._session_presence is None:
            self._session_presence = SessionPresenceHub(self)
        return self._session_presence

    def list_parties(self) -> list[PartyConfig]:
        return list(self._parties.values())

    def get_party(self, slug: str) -> PartyConfig | None:
        return self._parties.get(slug)

    def register_agent(self, username: str, color: str) -> Agent:
        agent = Agent(agent_id=uuid.uuid4().hex, username=username, color=color)
        self._agents[agent.agent_id] = agent
        return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def delete_agent(self, agent_id: str) -> bool:
        return self._agents.pop(agent_id, None) is not None

    def world_of(self, principal_key: str) -> str | None:
        """Return the slug of the party the principal is currently in.

        ``principal_key`` is ``"<kind>:<id>"``. Returns ``None`` when the
        principal is not currently a participant in any world.
        """
        try:
            kind, ident = principal_key.split(":", 1)
        except ValueError:
            return None
        for slug, world in self._worlds.items():
            participant = world.participants.get(ident)
            if participant is not None and participant.kind == kind:
                return slug
        return None

    def principal_exists(self, principal) -> bool:
        """True iff the human session or agent registration is known."""
        kind = getattr(principal, "kind", None)
        ident = getattr(principal, "id", None)
        if kind is None and isinstance(principal, dict):
            kind = principal.get("kind")
            ident = principal.get("id")
        if kind == "human":
            return self.get_session(ident) is not None
        if kind == "agent":
            return self.get_agent(ident) is not None
        return False

    def get_or_create_world(self, slug: str) -> PartyWorld | None:
        party = self._parties.get(slug)
        if party is None:
            return None
        if slug not in self._worlds:
            self._worlds[slug] = PartyWorld(party)
        return self._worlds[slug]

    def get_or_create_hub(self, slug: str) -> PartyWorldHub | None:
        if slug not in self._parties:
            return None
        if slug in self._hubs:
            return self._hubs[slug]
        world = self.get_or_create_world(slug)
        assert world is not None
        hub = PartyWorldHub(world)
        self._hubs[slug] = hub
        return hub
