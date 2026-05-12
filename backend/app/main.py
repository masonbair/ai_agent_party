from fastapi import FastAPI

app = FastAPI(title="ai_agent_party")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
