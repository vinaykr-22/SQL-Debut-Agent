"""
SQLQueryDebugEnv: OpenEnv-style environment for SQL query debugging.
"""

from __future__ import annotations

import random
import sqlite3
from typing import Any, Optional

from pydantic import BaseModel, Field

from tasks import TASKS, Task

MAX_ATTEMPTS = 5
FORBIDDEN_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "replace",
    "attach",
    "pragma",
}


class SQLDebugObservation(BaseModel):
    task_name: str
    buggy_query: str
    schema_sql: str
    expected_rows: list[dict[str, Any]]
    task_description: str
    attempts_remaining: int
    done: bool = False


class SQLDebugAction(BaseModel):
    fixed_query: str = Field(..., description="The corrected SQL SELECT query")


class SQLDebugReward(BaseModel):
    value: float = Field(..., ge=0.0, le=1.0)
    grade: str


class SQLDebugStepResult(BaseModel):
    observation: SQLDebugObservation
    reward: float = Field(..., ge=0.0, le=1.0)
    done: bool
    info: dict[str, Any] = Field(default_factory=dict)


def _run_query(schema_sql: str, seed_sql: str, query: str) -> tuple[list[dict[str, Any]], Optional[str]]:
    try:
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.executescript(schema_sql)
        cur.executescript(seed_sql)
        con.commit()
        cur.execute(query)
        rows = [dict(row) for row in cur.fetchall()]
        con.close()
        return rows, None
    except sqlite3.Error as exc:
        return [], str(exc)


def _normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        normalized.append({k: (str(v) if v is not None else None) for k, v in row.items()})
    return sorted(normalized, key=lambda r: str(sorted(r.items())))


def _score(expected: list[dict[str, Any]], actual: list[dict[str, Any]]) -> tuple[float, str]:
    if not expected and not actual:
        return 1.0, "exact"

    n_expected = _normalize_rows(expected)
    n_actual = _normalize_rows(actual)

    if n_expected == n_actual:
        return 1.0, "exact"

    expected_cols = set(expected[0].keys()) if expected else set()
    actual_cols = set(actual[0].keys()) if actual else set()
    if expected_cols != actual_cols:
        return 0.0, "wrong_columns"

    expected_keys = [frozenset(r.items()) for r in n_expected]
    actual_keys = list(frozenset(r.items()) for r in n_actual)

    matches = 0
    for key in expected_keys:
        if key in actual_keys:
            actual_keys.remove(key)
            matches += 1

    precision = matches / len(n_actual) if n_actual else 0.0
    recall = matches / len(n_expected) if n_expected else 0.0
    if precision + recall == 0:
        return 0.0, "no_overlap"

    f1 = (2 * precision * recall) / (precision + recall)
    return round(0.2 + 0.65 * f1, 4), "partial"


def _is_undesirable_query(query: str) -> Optional[str]:
    q = query.strip().lower()
    if not q:
        return "empty_query"

    tokens = set(q.replace(";", " ").replace("\n", " ").split())
    forbidden = sorted(FORBIDDEN_KEYWORDS.intersection(tokens))
    if forbidden:
        return f"forbidden_keyword:{forbidden[0]}"

    starts_valid = q.startswith("select") or q.startswith("with")
    if not starts_valid:
        return "non_select_query"

    # Disallow multiple SQL statements in one action.
    statements = [s.strip() for s in query.split(";") if s.strip()]
    if len(statements) > 1:
        return "multiple_statements"

    return None


class SQLQueryDebugEnv:
    def __init__(self) -> None:
        self._task: Optional[Task] = None
        self._expected_rows: list[dict[str, Any]] = []
        self._attempts_remaining = MAX_ATTEMPTS
        self._done = False

    def reset(self, task_name: Optional[str] = None) -> SQLDebugObservation:
        if task_name is None:
            task_name = random.choice(list(TASKS.keys()))

        if task_name not in TASKS:
            raise ValueError(f"Unknown task '{task_name}'. Available: {list(TASKS.keys())}")

        self._task = TASKS[task_name]
        self._attempts_remaining = MAX_ATTEMPTS
        self._done = False

        self._expected_rows, err = _run_query(
            self._task.schema_sql,
            self._task.seed_sql,
            self._task.correct_query,
        )
        if err:
            raise RuntimeError(f"Correct query failed for task '{task_name}': {err}")

        return self._build_observation()

    def step(self, action: SQLDebugAction) -> SQLDebugStepResult:
        if self._task is None:
            raise RuntimeError("Call reset() before step().")

        if self._done:
            return SQLDebugStepResult(
                observation=self._build_observation(),
                reward=0.0,
                done=True,
                info={"error": "Episode already done. Call reset()."},
            )

        self._attempts_remaining -= 1
        undesirable_reason = _is_undesirable_query(action.fixed_query)

        if undesirable_reason:
            reward = 0.0
            grade = "undesirable"
            info: dict[str, Any] = {
                "error": undesirable_reason,
                "undesirable_behavior": True,
            }
        else:
            actual_rows, sql_error = _run_query(
                self._task.schema_sql,
                self._task.seed_sql,
                action.fixed_query,
            )
            if sql_error:
                reward = 0.0
                grade = "sql_error"
                info = {"error": sql_error, "sql_error": True}
            else:
                reward, grade = _score(self._expected_rows, actual_rows)
                info = {
                    "error": None,
                    "expected_row_count": len(self._expected_rows),
                    "actual_row_count": len(actual_rows),
                }

        if reward == 1.0 or self._attempts_remaining == 0:
            self._done = True

        info["grade"] = grade
        info["attempts_remaining"] = self._attempts_remaining

        return SQLDebugStepResult(
            observation=self._build_observation(),
            reward=reward,
            done=self._done,
            info=info,
        )

    def state(self) -> dict[str, Any]:
        if self._task is None:
            return {"initialized": False}
        return {
            "initialized": True,
            "task_name": self._task.task_name,
            "difficulty": self._task.difficulty,
            "attempts_remaining": self._attempts_remaining,
            "done": self._done,
        }

    def close(self) -> None:
        self._task = None
        self._expected_rows = []
        self._attempts_remaining = MAX_ATTEMPTS
        self._done = False

    def _build_observation(self) -> SQLDebugObservation:
        assert self._task is not None
        return SQLDebugObservation(
            task_name=self._task.task_name,
            buggy_query=self._task.buggy_query,
            schema_sql=self._task.schema_sql,
            expected_rows=self._expected_rows,
            task_description=self._task.task_description,
            attempts_remaining=self._attempts_remaining,
            done=self._done,
        )


__all__ = [
    "SQLQueryDebugEnv",
    "SQLDebugObservation",
    "SQLDebugAction",
    "SQLDebugReward",
    "SQLDebugStepResult",
]
