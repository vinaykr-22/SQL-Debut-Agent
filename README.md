---
title: SQL Query Debug Agent Env
emoji: "🛠️"
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
tags:
  - openenv
  - sql
  - debugging
  - real-world
---

# SQL Query Debug Agent Environment

An OpenEnv-compliant reinforcement-learning style environment where an AI agent receives a broken SQL query and must submit a corrected query.

## Motivation

SQL query debugging is a real, repeatable task data analysts and backend engineers perform daily. This environment provides deterministic scoring and a realistic workflow for agent evaluation.

## Functional Design

### Observation Space

Each observation includes:
- task_name
- buggy_query
- schema_sql
- expected_rows
- task_description
- attempts_remaining
- done

### Action Space

The action is one text field:
- fixed_query: corrected SQL SELECT query

### Reward Function

- 1.0 for exact row match (order-insensitive)
- 0.2 to 0.85 for partial overlap with correct columns
- 0.0 for wrong columns, SQL errors, or no overlap
- 0.0 with explicit undesirable behavior flag for destructive or invalid actions:
  - non-SELECT queries
  - forbidden SQL keywords (UPDATE, DELETE, DROP, etc.)
  - multiple SQL statements in one action

This supplies graded trajectory signal, not just end-of-episode binary success.

## Tasks

1. active_customers_last_90_days (easy)
- Fix join-key bug to return active customers in last 90 days.

2. support_ticket_backlog_by_priority (medium)
- Fix status filtering and ordering to compute open backlog by priority.

3. monthly_subscription_margin (hard)
- Fix faulty join and add HAVING filter to return only profitable months.

4. churn_risk_accounts_with_refunds (expert-level hard)
- Compute account-level refund ratio and return only high-risk accounts.

## Project Structure

- environment.py: environment, Pydantic models, deterministic grader
- tasks.py: task definitions and SQL fixtures
- server.py: FastAPI HTTP interface
- openenv.yaml: OpenEnv metadata
- inference.py: OpenAI baseline script
- Dockerfile: container runtime
- requirements.txt: Python dependencies

## Setup

1. Install dependencies

```bash
pip install -r requirements.txt
```

2. Run API server

```bash
uvicorn server:app --host 0.0.0.0 --port 7860
# or
python server.py
```

The root URL now serves a built-in user interface for manual testing:

```bash
http://localhost:7860/
```

OpenEnv API endpoints remain unchanged at /health, /metadata, /schema, /reset, /step, and /state.

The UI also includes an Analyze & Auto-Fix action:
- paste a buggy query
- get a bug summary
- auto-fill the suggested corrected query

Programmatic analysis endpoint:

```bash
POST /analyze
{
  "task_name": "active_customers_last_90_days",
  "buggy_query": "SELECT ..."
}
```

3. Test endpoints

```bash
curl http://localhost:7860/health

curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_name": "active_customers_last_90_days"}'

curl -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{"fixed_query": "SELECT c.name, MAX(o.order_date) AS last_order_date FROM customers c JOIN orders o ON c.id = o.customer_id WHERE o.order_date >= date('"'"'2026-01-01'"'"', '"'"'-90 day'"'"') GROUP BY c.name ORDER BY c.name"}'
```

## Baseline Inference Script

Set credentials and run:

```bash
export OPENAI_API_KEY=sk-...
# optional
# export MODEL_NAME=gpt-4o-mini
# export API_BASE_URL=https://api.openai.com/v1
# export RUN_EXPERT_TASK=1   # include the fourth expert-level task

python inference.py
```

By default, the baseline runs the core 3 tasks required by the rubric.
Set RUN_EXPERT_TASK=1 to include the additional expert task.

Example log format:

```text
[START] task=active_customers_last_90_days env=sql-query-debug-agent-env model=gpt-4o-mini
[STEP] step=1 action='SELECT ...' reward=1.00 done=true error=null
[END] success=true steps=1 score=1.000 rewards=1.000
```

## Baseline Scores (illustrative)

These vary by model and prompting. Typical zero-shot pattern:

- easy task: around 1.0
- medium task: around 0.6 to 1.0
- hard task: around 0.3 to 0.9

With RUN_EXPERT_TASK=1, the fourth expert task is typically harder and may score lower.

## OpenEnv Validation

Run validation in your OpenEnv toolchain:

```bash
openenv validate .
```

## Local Requirement Verification

Run the built-in checker:

```bash
python verify_requirements.py
```

Run all checks in one command (local checks + OpenEnv validate):

```bash
python run_checks.py
```

If OpenEnv CLI is not installed yet, run:

```bash
python run_checks.py --skip-openenv
```

## Docker

```bash
docker build -t sql-query-debug-agent-env .
docker run -p 7860:7860 sql-query-debug-agent-env
```

## CI Automation

This repository includes a GitHub Actions workflow at .github/workflows/ci.yml.

On every push and pull request, CI will:
- install dependencies
- run verify_requirements.py
- run run_checks.py --skip-openenv
