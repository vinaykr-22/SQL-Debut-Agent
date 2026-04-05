"""
FastAPI server exposing SQLQueryDebugEnv over HTTP.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from environment import SQLQueryDebugEnv, SQLDebugAction

app = FastAPI(
    title="SQL Query Debug Agent Env",
    description="OpenEnv environment where agents fix broken SQL queries.",
    version="1.0.0",
)

env = SQLQueryDebugEnv()
UI_PATH = Path(__file__).parent / "ui" / "index.html"


class ResetRequest(BaseModel):
    task_name: Optional[str] = None


class StepRequest(BaseModel):
    fixed_query: str


@app.get("/")
def root() -> FileResponse:
    return FileResponse(UI_PATH)


@app.get("/ui")
def ui() -> FileResponse:
    return FileResponse(UI_PATH)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/metadata")
def metadata() -> dict[str, Any]:
    return {
        "name": "sql-query-debug-agent-env",
        "version": "1.0.0",
        "description": "Environment for SQL query debugging with deterministic graders.",
        "tags": ["openenv", "sql", "debugging", "real-world"],
        "tasks": [
            {"name": "active_customers_last_90_days", "difficulty": "easy"},
            {"name": "support_ticket_backlog_by_priority", "difficulty": "medium"},
            {"name": "monthly_subscription_margin", "difficulty": "hard"},
            {"name": "churn_risk_accounts_with_refunds", "difficulty": "hard"},
        ],
        "reward_range": [0.0, 1.0],
        "max_steps": 5,
    }


@app.get("/schema")
def schema() -> dict[str, Any]:
    return {
        "action": {
            "type": "object",
            "properties": {
                "fixed_query": {
                    "type": "string",
                    "description": "A corrected SQL SELECT query",
                }
            },
            "required": ["fixed_query"],
        },
        "observation": {
            "type": "object",
            "properties": {
                "task_name": {"type": "string"},
                "buggy_query": {"type": "string"},
                "schema_sql": {"type": "string"},
                "expected_rows": {"type": "array"},
                "task_description": {"type": "string"},
                "attempts_remaining": {"type": "integer"},
                "done": {"type": "boolean"},
            },
        },
    }


@app.post("/reset")
def reset(body: ResetRequest = ResetRequest()) -> dict[str, Any]:
    try:
        obs = env.reset(body.task_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return obs.model_dump()


@app.post("/step")
def step(body: StepRequest) -> dict[str, Any]:
    if not body.fixed_query.strip():
        raise HTTPException(status_code=400, detail="fixed_query must not be empty")

    try:
        result = env.step(SQLDebugAction(fixed_query=body.fixed_query))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "observation": result.observation.model_dump(),
        "reward": result.reward,
        "done": result.done,
        "info": result.info,
    }


@app.get("/state")
def state() -> dict[str, Any]:
    return env.state()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=7860, reload=False)
