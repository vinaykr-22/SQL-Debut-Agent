"""
FastAPI server exposing SQLQueryDebugEnv over HTTP.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from environment import SQLQueryDebugEnv, SQLDebugAction
from tasks import TASKS, Task

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


class AnalyzeRequest(BaseModel):
    buggy_query: str
    task_name: Optional[str] = None


BUG_SUMMARIES: dict[str, str] = {
    "active_customers_last_90_days": (
        "JOIN uses the wrong key (`orders.id` instead of `orders.customer_id`), "
        "which drops valid customer-order matches."
    ),
    "support_ticket_backlog_by_priority": (
        "Filter uses `status = 'closed'` but backlog should count `status = 'open'`."
    ),
    "monthly_subscription_margin": (
        "JOIN compares month to cost (`s.month = c.infra_cost`) instead of month-to-month, "
        "and the profitable-month HAVING filter is missing."
    ),
    "churn_risk_accounts_with_refunds": (
        "Refund JOIN uses account_id against invoice_id, and the query misses the required "
        "refund-ratio threshold filter."
    ),
}


def _normalise_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql.strip().lower())


def _task_similarity(input_query: str, task: Task) -> float:
    return SequenceMatcher(
        None,
        _normalise_sql(input_query),
        _normalise_sql(task.buggy_query),
    ).ratio()


def _pick_task_for_query(task_name: Optional[str], buggy_query: str) -> tuple[Task, float]:
    if task_name:
        if task_name not in TASKS:
            raise ValueError(f"Unknown task '{task_name}'. Available: {list(TASKS.keys())}")
        selected = TASKS[task_name]
        return selected, _task_similarity(buggy_query, selected)

    scored = [(_task_similarity(buggy_query, task), task) for task in TASKS.values()]
    confidence, selected = max(scored, key=lambda x: x[0])
    return selected, confidence


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


@app.post("/analyze")
def analyze(body: AnalyzeRequest) -> dict[str, Any]:
    if not body.buggy_query.strip():
        raise HTTPException(status_code=400, detail="buggy_query must not be empty")

    try:
        task, confidence = _pick_task_for_query(body.task_name, body.buggy_query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    recognized = confidence >= 0.45

    return {
        "recognized": recognized,
        "matched_task": task.task_name,
        "confidence": round(confidence, 4),
        "bug_summary": BUG_SUMMARIES.get(task.task_name, "Bug detected in query logic."),
        "corrected_query": task.correct_query,
        "hint": task.task_description,
    }


@app.get("/state")
def state() -> dict[str, Any]:
    return env.state()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=7860, reload=False)
