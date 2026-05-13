from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, field_validator

from app.events import Agent
from app.store import Store
from app.validation import ALLOWED_COLORS, USERNAME_REGEX

router = APIRouter(prefix="/api/agents")


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


class CreateAgentRequest(BaseModel):
    username: str
    color: str

    @field_validator("username")
    @classmethod
    def _check_username(cls, v: str) -> str:
        if USERNAME_REGEX.fullmatch(v) is None:
            raise ValueError("username must be 2-20 letters/digits")
        return v


@router.post("", response_model=Agent)
def create_agent(
    body: CreateAgentRequest, store: Store = Depends(_store_dep)
) -> Agent:
    if body.color not in ALLOWED_COLORS:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_color",
                "allowed_colors": list(ALLOWED_COLORS),
            },
        )
    return store.register_agent(username=body.username, color=body.color)


@router.get("/{agent_id}", response_model=Agent)
def get_agent(agent_id: str, store: Store = Depends(_store_dep)) -> Agent:
    agent = store.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: str, store: Store = Depends(_store_dep)) -> Response:
    if not store.delete_agent(agent_id):
        raise HTTPException(status_code=404, detail="agent not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
