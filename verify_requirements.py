"""
Automated local requirement checks for sql-query-debug-agent-env.

Usage:
  python verify_requirements.py
"""

from __future__ import annotations

from pathlib import Path
import sys

from environment import SQLQueryDebugEnv, SQLDebugAction
from tasks import TASKS


ROOT = Path(__file__).resolve().parent


def check(condition: bool, message: str) -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {message}")
    return condition


def main() -> int:
    ok = True

    required_files = [
        "environment.py",
        "tasks.py",
        "server.py",
        "openenv.yaml",
        "inference.py",
        "Dockerfile",
        "README.md",
    ]
    for name in required_files:
        ok &= check((ROOT / name).exists(), f"required file exists: {name}")

    task_count = len(TASKS)
    ok &= check(task_count >= 3, "at least 3 tasks are defined")

    difficulties = {t.difficulty for t in TASKS.values()}
    ok &= check({"easy", "medium", "hard"}.issubset(difficulties), "difficulty spread includes easy, medium, hard")

    env = SQLQueryDebugEnv()

    # Grader determinism and perfect-score check with each task's known-correct query.
    for task_name, task in TASKS.items():
        obs = env.reset(task_name)
        result = env.step(SQLDebugAction(fixed_query=task.correct_query))
        ok &= check(obs.task_name == task_name, f"reset returns expected task: {task_name}")
        ok &= check(result.reward == 1.0, f"grader returns 1.0 for known-correct query: {task_name}")

    env.reset("active_customers_last_90_days")
    undesirable = env.step(SQLDebugAction(fixed_query="DROP TABLE customers"))
    ok &= check(undesirable.reward == 0.0, "undesirable destructive action is penalized")
    ok &= check(bool(undesirable.info.get("undesirable_behavior")), "undesirable behavior is explicitly flagged")

    inference_text = (ROOT / "inference.py").read_text(encoding="utf-8")
    ok &= check("OPENAI_API_KEY" in inference_text, "baseline script reads OPENAI_API_KEY")

    openenv_text = (ROOT / "openenv.yaml").read_text(encoding="utf-8")
    ok &= check("reward_range:" in openenv_text and "max_steps:" in openenv_text, "openenv.yaml includes key metadata")

    docker_text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    ok &= check("uvicorn" in docker_text and "server:app" in docker_text, "Dockerfile starts API server")

    env.close()

    if ok:
        print("\nAll requirement checks passed.")
        return 0

    print("\nSome checks failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
