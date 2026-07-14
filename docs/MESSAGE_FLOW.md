# Message Flow

This documents how a Telegram message actually moves through the system today. It reflects the live n8n workflow, not the original phase plan — see [`PLAN.md`](./PLAN.md) for the higher-level roadmap.

## Main flow — a message arrives

```mermaid
flowchart TD
    A[Telegram message] --> B{Authorized user?}
    B -->|no| Z[Ignored]
    B -->|yes| C[Detect /az tag]
    C --> D[Fetch last 6 turns from conversation_log]
    D --> E["Router: Qwen2.5-3B<br/>classify + maybe answer"]
    E --> F{type}

    F -->|simple, generic/English| G[3B answers directly]
    F -->|simple, needs personal context, or /az tag| H[Embed message]
    F -->|reminder| R1[Extract content + due_date]
    F -->|project| P1["Extract action / name / status / deadline"]
    F -->|heavy, presentation, content| U["Placeholder reply<br/>(not built yet)"]

    H --> I["Search Qdrant:<br/>profile_facts + conversation_memory"]
    I --> J[Inject facts into prompt]
    J --> K["Local model: Qwen2.5-14B<br/>answers with context"]

    R1 --> R2{Has due date?}
    R2 -->|yes| R3[INSERT INTO tasks]
    R2 -->|no| R4[Ask for date/time]
    R3 --> R5[Confirm reminder]

    P1 --> P2{create or update?}
    P2 -->|create| P3[INSERT INTO projects]
    P2 -->|update| P4[Find project by name]
    P4 --> P5{Found?}
    P5 -->|yes| P6[UPDATE projects]
    P5 -->|no| P7[Ask to create instead]
    P3 --> P8[Confirm project]
    P6 --> P8

    G --> L[Log turn to conversation_log]
    K --> L
    R4 --> L
    R5 --> L
    P7 --> L
    P8 --> L
    U --> L

    G -.->|if memorable| M["3B: worth remembering?"]
    K -.->|if memorable| M
    M -->|yes| N[Embed fact]
    N --> O["Upsert into Qdrant<br/>conversation_memory"]
```

Notes:
- **Only n8n ever talks to Qdrant or Postgres.** No model has tool/function-calling access to either — every LLM call here is plain text in, text out. n8n does the embedding, the vector search, and pastes results into the next prompt as plain text.
- The 3B router is also the model used for reminder/project extraction and the "worth remembering?" memory check — it's the cheap, fast model reused across several narrow-purpose calls, not just classification.
- The 14B local model is the only one with RAG context injected into its prompt; the 3B router never sees retrieved facts, which is why it defers personal questions instead of answering them itself.
- "Last 6 turns" conversation history is injected into the router, reminder-extraction, and project-extraction prompts so short follow-ups ("yes", "in 10 minutes") resolve correctly against what was just asked.

## Background workflows (separate from the message flow above)

```mermaid
flowchart LR
    T1[Every 1 minute] --> T2["SELECT due tasks<br/>WHERE remind_count = 0"] --> T3[Send Telegram notification] --> T4[UPDATE remind_count]
    D1["Daily, 9:00 Baku time"] --> D2["SELECT active projects<br/>+ upcoming/overdue tasks"] --> D3[Build digest text] --> D4[Send Telegram digest]
```

- **Cron - Reminder Checker**: runs every minute, fires a reminder exactly once when its `due_date` arrives.
- **Cron - Daily Digest**: runs once a day, summarizes active projects and upcoming reminders in one message.

## RunPod endpoints in play

| Endpoint | Model | Called by | Purpose |
|---|---|---|---|
| Router | Qwen2.5-3B-Instruct | n8n | Classify every message; answer generic `simple` questions directly; extract reminder/project structure; judge memorability |
| Local | Qwen2.5-14B-Instruct | n8n | Answer questions needing personal context (RAG-injected) |
| Embedding | multilingual-e5-small | n8n | Turn text into vectors for Qdrant search/upsert |

All three scale to zero when idle (`workersMin: 0`, `idleTimeout: 120s`) — cost is paid in cold-start latency, not idle GPU time. See [`PLAN.md`](./PLAN.md) for the reasoning behind that tradeoff.
