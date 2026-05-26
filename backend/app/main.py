import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import db as db_module
from app.errors import FORBIDDEN, HTTP_ERROR, METHOD_NOT_ALLOWED, NOT_FOUND, UNAUTHORIZED, VALIDATION_ERROR, envelope
from app.routes import agent_guide as agent_guide_routes
from app.routes import agents as agents_routes
from app.routes import dm as dm_routes
from app.routes import inbox_ws as inbox_ws_routes
from app.routes import lighting as lighting_routes
from app.routes import module_drawboard as module_drawboard_routes
from app.routes import module_notes as module_notes_routes
from app.routes import history as history_routes
from app.routes import parties as parties_routes
from app.routes import party_actions as party_actions_routes
from app.routes import reactions as reactions_routes
from app.routes import session as session_routes
from app.store import Store

app = FastAPI(title="ai_agent_party")


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Wrap any HTTPException whose detail is still a bare string into
    the standard envelope. HTTPExceptions raised via ``http_envelope``
    already carry a dict detail; we pass those through untouched.
    """
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        # Already enveloped.
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    # Map known framework status codes onto stable codes + safe default messages.
    # Never leak raw Starlette internal strings as the public message.
    code_map = {
        404: NOT_FOUND,
        405: METHOD_NOT_ALLOWED,
        401: UNAUTHORIZED,
        403: FORBIDDEN,
    }
    code = code_map.get(exc.status_code, HTTP_ERROR)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": envelope(code)},
    )


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    fields = []
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path")]
        fields.append(
            {
                "field": ".".join(loc) if loc else None,
                "message": err.get("msg", ""),
            }
        )
    return JSONResponse(
        status_code=422,
        content={"detail": envelope(VALIDATION_ERROR, fields=fields)},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_store = Store()


@app.on_event("startup")
def _open_db() -> None:
    path = os.getenv("OPENPARTY_DB_PATH", "backend/data/openparty.sqlite")
    if path != ":memory:":
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
    _store.db = db_module.init_db(path)


@app.on_event("shutdown")
def _close_db() -> None:
    db_module.close_db(_store.db)
    _store.db = None


def get_store() -> Store:
    return _store


app.dependency_overrides[session_routes._store_dep] = get_store
app.dependency_overrides[parties_routes._store_dep] = get_store
app.dependency_overrides[agents_routes._store_dep] = get_store
app.dependency_overrides[party_actions_routes._store_dep] = get_store
app.dependency_overrides[dm_routes._store_dep] = get_store
app.dependency_overrides[inbox_ws_routes._store_dep] = get_store
app.dependency_overrides[reactions_routes._store_dep] = get_store
app.dependency_overrides[lighting_routes._store_dep] = get_store
app.dependency_overrides[module_notes_routes._store_dep] = get_store
app.dependency_overrides[module_drawboard_routes._store_dep] = get_store
app.dependency_overrides[history_routes._store_dep] = get_store
app.include_router(session_routes.router)
app.include_router(parties_routes.router)
app.include_router(agents_routes.router)
app.include_router(party_actions_routes.router)
app.include_router(agent_guide_routes.router)
app.include_router(dm_routes.router)
app.include_router(inbox_ws_routes.router)
app.include_router(reactions_routes.router)
app.include_router(lighting_routes.router)
app.include_router(module_notes_routes.router)
app.include_router(module_drawboard_routes.router)
app.include_router(history_routes.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
