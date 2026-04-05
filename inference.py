"""
Baseline inference runner for SQLQueryDebugEnv.

Required env var:
- OPENAI_API_KEY

Optional env vars:
- MODEL_NAME (default: gpt-4o-mini)
- API_BASE_URL (default: https://api.openai.com/v1)
"""

from __future__ import annotations

import os
import re
import sys

from openai import OpenAI

from environment import SQLQueryDebugEnv, SQLDebugAction, SQLDebugObservation

MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o-mini")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

CORE_TASK_NAMES = [
    "active_customers_last_90_days",
    "support_ticket_backlog_by_priority",
    "monthly_subscription_margin",
]

EXPERT_TASK_NAME = "churn_risk_accounts_with_refunds"

MAX_STEPS = 5
ENV_NAME = "sql-query-debug-agent-env"

SYSTEM_PROMPT = (
    "You are a SQL debugging assistant. "
    "You will get a broken SQL query, schema, and expected rows. "
    "Return only the corrected SQL query. No explanation."
)

FENCE_RE = re.compile(r"```(?:sql)?\\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_sql(text: str) -> str:
    match = FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def build_user_prompt(obs: SQLDebugObservation) -> str:
    preview = obs.expected_rows[:5]
    preview_text = "\\n".join(str(row) for row in preview)
    more = len(obs.expected_rows) - len(preview)
    if more > 0:
        preview_text += f"\\n... ({more} more rows)"

    return (
        f"Task: {obs.task_description}\\n\\n"
        f"Schema:\\n{obs.schema_sql}\\n\\n"
        f"Buggy query:\\n{obs.buggy_query}\\n\\n"
        f"Expected rows ({len(obs.expected_rows)}):\\n{preview_text}\\n\\n"
        f"Attempts remaining: {obs.attempts_remaining}\\n"
    )


def run_task(client: OpenAI, env: SQLQueryDebugEnv, task_name: str) -> None:
    obs = env.reset(task_name)
    messages: list[dict[str, str]] = []
    rewards: list[float] = []

    print(f"[START] task={task_name} env={ENV_NAME} model={MODEL_NAME}", flush=True)

    done = False
    step_num = 0
    while not done and step_num < MAX_STEPS:
        step_num += 1

        user_prompt = build_user_prompt(obs)
        messages.append({"role": "user", "content": user_prompt})

        try:
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                temperature=0.0,
                max_tokens=400,
            )
            model_text = resp.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            model_text = obs.buggy_query
            print(f"[WARN] API error at step={step_num}: {exc}", file=sys.stderr, flush=True)

        sql = extract_sql(model_text)
        messages.append({"role": "assistant", "content": sql})

        result = env.step(SQLDebugAction(fixed_query=sql))
        rewards.append(result.reward)
        done = result.done

        error_str = result.info.get("error") or "null"
        print(
            f"[STEP] step={step_num} action={sql.replace(chr(10), ' ')!r} "
            f"reward={result.reward:.2f} done={'true' if done else 'false'} error={error_str}",
            flush=True,
        )

        obs = result.observation

    success = any(r == 1.0 for r in rewards)
    best_score = max(rewards) if rewards else 0.0
    rewards_joined = ",".join(f"{r:.3f}" for r in rewards)

    print(
        f"[END] success={'true' if success else 'false'} steps={step_num} "
        f"score={best_score:.3f} rewards={rewards_joined}",
        flush=True,
    )


def main() -> None:
    if not OPENAI_API_KEY:
        print("[ERROR] OPENAI_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=OPENAI_API_KEY, base_url=API_BASE_URL)
    env = SQLQueryDebugEnv()

    run_expert = os.environ.get("RUN_EXPERT_TASK", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    task_names = list(CORE_TASK_NAMES)
    if run_expert:
        task_names.append(EXPERT_TASK_NAME)

    for task in task_names:
        run_task(client, env, task)

    env.close()


if __name__ == "__main__":
    main()
