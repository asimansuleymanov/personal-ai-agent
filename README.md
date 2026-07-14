# Personal AI Agent

A lightweight, always-on personal assistant that lives in Telegram. It handles simple tasks (reminders, schedule, quick questions) itself using a local LLM, and routes heavier tasks (code, deep analysis, content generation, presentations) to external AI APIs — automatically choosing the best option based on cost and quality.

## What it does

- **Single interface, any device** — talk to it through Telegram from phone or laptop
- **Personal memory (RAG)** — knows your profile, ongoing projects, and context via a vector database
- **Project & deadline tracking** — works, personal errands, or travel plans (e.g. "Tbilisi flight tickets open on the 20th, remind me") all tracked in one place
- **Smart task routing** — a small router model classifies each request and decides: handle locally, or send to a stronger external model
- **Reminders** — background cron jobs check deadlines and nudge you proactively
- **Content generation** — drafts for emails/messages, and presentation decks on request

## Architecture

```
Telegram Bot → n8n (orchestrator, 24/7) → Router LLM → Local LLM | External AI APIs
                     │
                     ├─ Postgres  (projects, tasks, reminders)
                     └─ Qdrant    (personal memory / RAG)
```

- **Orchestration:** n8n
- **Database:** PostgreSQL
- **Vector memory:** Qdrant
- **Local inference:** Ollama / vLLM on RunPod Serverless (on-demand GPU)
- **External AI:** Claude API (Haiku for cheap/fast tasks, Sonnet for higher-quality content)
- **Hosting:** Hetzner Cloud (orchestrator VM, always-on)

Full architecture, deployment plan, task breakdown, and token/cost estimates: see [`docs/PLAN.md`](docs/PLAN.md). For how a message actually moves through the live system today (routing, RAG retrieval, reminders/projects, cron jobs), see [`docs/MESSAGE_FLOW.md`](docs/MESSAGE_FLOW.md).

## Status

🚧 In development — Phases 1–4 (infrastructure, router/local LLM, memory/RAG, reminders & projects) are live and working end-to-end. Remaining: project deadline notifications, and Phase 5 (heavy task routing to external AI APIs, presentations, content drafts) hasn't started yet.

## Repo structure

```
.
├── docs/
│   ├── PLAN.md            # Full architecture & project plan
│   └── MESSAGE_FLOW.md    # How a message moves through the live system
├── docker-compose.yml     # n8n + Postgres + Qdrant + Caddy
├── db/schema.sql          # Database schema
└── router-prompts/        # Router, local-model, and extraction prompts
```

## Requirements

- Hetzner Cloud account
- RunPod account
- Anthropic (Claude) API key
- Telegram Bot token (via [@BotFather](https://t.me/BotFather))
- A domain name (for HTTPS webhook — required by Telegram)

## Roadmap

See [`docs/PLAN.md`](docs/PLAN.md) for the full phased task list (infrastructure → router/local LLM → memory/RAG → projects & reminders → heavy task routing → Gmail/Calendar integration).
