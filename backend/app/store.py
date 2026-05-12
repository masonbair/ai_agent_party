import uuid

from app.models import PartyConfig, User
from app.parties_data import PARTY_REGISTRY


class Store:
    def __init__(self) -> None:
        self._sessions: dict[str, User] = {}
        self._parties: dict[str, PartyConfig] = dict(PARTY_REGISTRY)

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
