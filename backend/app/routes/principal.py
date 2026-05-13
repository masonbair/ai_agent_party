from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel

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
            raise HTTPException(status_code=401, detail="principal_unknown")
        return ResolvedPrincipal(
            id=user.session_id,
            kind="human",
            username=user.username,
            color=user.color,
        )
    agent = store.get_agent(principal.id)
    if agent is None:
        raise HTTPException(status_code=401, detail="principal_unknown")
    return ResolvedPrincipal(
        id=agent.agent_id,
        kind="agent",
        username=agent.username,
        color=agent.color,
    )
