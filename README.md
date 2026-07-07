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

Full architecture, deployment plan, task breakdown, and token/cost estimates: see [`PLAN.md`](./PLAN.md).

## Status

🚧 In development — currently in **Phase 1: Infrastructure setup**.

## Repo structure

```
.
├── PLAN.md            # Full architecture & project plan
├── docker-compose.yml # n8n + Postgres + Qdrant + Caddy
├── n8n/                # Exported n8n workflows
├── db/schema.sql       # Database schema
└── router-prompts/     # Router & task-classification prompts
```

## Requirements

- Hetzner Cloud account
- RunPod account
- Anthropic (Claude) API key
- Telegram Bot token (via [@BotFather](https://t.me/BotFather))
- A domain name (for HTTPS webhook — required by Telegram)

## Roadmap

See [`PLAN.md`](./PLAN.md) for the full phased task list (infrastructure → router/local LLM → memory/RAG → projects & reminders → heavy task routing → Gmail/Calendar integration).
