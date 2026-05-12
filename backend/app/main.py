from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import parties as parties_routes
from app.routes import session as session_routes
from app.store import Store

app = FastAPI(title="ai_agent_party")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_store = Store()


def get_store() -> Store:
    return _store


app.dependency_overrides[session_routes._store_dep] = get_store
app.dependency_overrides[parties_routes._store_dep] = get_store
app.include_router(session_routes.router)
app.include_router(parties_routes.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
