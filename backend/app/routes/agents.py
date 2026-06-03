from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, field_validator

from app.errors import AGENT_NOT_FOUND, INVALID_COLOR, http_envelope, envelope
from app.events import Agent
from app.store import Store
from app.validation import ALLOWED_COLORS, validate_username
from fastapi import HTTPException

router = APIRouter(prefix="/api/agents")


ALLOWED_STYLES = ("chatty", "ambient", "reactive")
INVALID_STYLE = "invalid_style"


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


class CreateAgentRequest(BaseModel):
    username: str
    color: str
    style: str = "reactive"

    @field_validator("username")
    @classmethod
    def _check_username(cls, v: str) -> str:
        return validate_username(v)


@router.post("", response_model=Agent)
def create_agent(
    body: CreateAgentRequest, store: Store = Depends(_store_dep)
) -> Agent:
    if body.color not in ALLOWED_COLORS:
        raise http_envelope(
            422, INVALID_COLOR, allowed_colors=list(ALLOWED_COLORS)
        )
    if body.style not in ALLOWED_STYLES:
        raise HTTPException(
            status_code=422,
            detail=envelope(
                INVALID_STYLE,
                message="The provided style is not in the allow-list.",
                allowed_styles=list(ALLOWED_STYLES),
            ),
        )
    return store.register_agent(
        username=body.username, color=body.color, style=body.style
    )


@router.get("/{agent_id}", response_model=Agent)
def get_agent(agent_id: str, store: Store = Depends(_store_dep)) -> Agent:
    agent = store.get_agent(agent_id)
    if agent is None:
        raise http_envelope(404, AGENT_NOT_FOUND)
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: str, store: Store = Depends(_store_dep)) -> Response:
    if not store.delete_agent(agent_id):
        raise http_envelope(404, AGENT_NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
