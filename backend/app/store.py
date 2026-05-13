import uuid

from app.events import Agent
from app.models import PartyConfig, User
from app.parties_data import PARTY_REGISTRY
from app.realtime import PartyWorldHub
from app.world import PartyWorld


class Store:
    def __init__(self) -> None:
        self._sessions: dict[str, User] = {}
        self._parties: dict[str, PartyConfig] = dict(PARTY_REGISTRY)
        self._agents: dict[str, Agent] = {}
        self._worlds: dict[str, PartyWorld] = {}
        self._hubs: dict[str, PartyWorldHub] = {}

    def create_session(self, username: str, color: str) -> User:
        session_id = uuid.uuid4().hex
        user = User(session_id=session_id, username=username, color=color)
        self._sessions[session_id] = user
        return user

    def get_session(self, session_id: str) -> User | None:
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

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
