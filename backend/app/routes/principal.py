from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from app.errors import PRINCIPAL_UNKNOWN, http_envelope
from app.store import Store


class Principal(BaseModel):
    kind: Literal["human", "agent"]
    id: str


@dataclass
class ResolvedPrincipal:
    id: str
    kind: Literal["human", "agent"]
    username: str
    color: str


def resolve_principal(store: Store, principal: Principal) -> ResolvedPrincipal:
    if principal.kind == "human":
        user = store.get_session(principal.id)
        if user is None:
            raise http_envelope(401, PRINCIPAL_UNKNOWN)
        return ResolvedPrincipal(
            id=user.session_id,
            kind="human",
            username=user.username,
            color=user.color,
        )
    agent = store.get_agent(principal.id)
    if agent is None:
        raise http_envelope(401, PRINCIPAL_UNKNOWN)
    return ResolvedPrincipal(
        id=agent.agent_id,
        kind="agent",
        username=agent.username,
        color=agent.color,
    )
