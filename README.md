# Munim AI - Har dukaan ka apna AI Munim

A proactive, voice-first, multi-agent AI copilot for Paytm merchants (Paytm Build for India AI Hackathon, Track 1: Merchant Growth AI).
It does not just show dashboards. It speaks first, proposes actions, **waits for the merchant's approval**, executes, and measures the outcome.

```
Insight -> Recommendation -> One-tap / voice approval -> Action -> Measured outcome
```

## What works end to end

| Feature | How it works |
| --- | --- |
| 30-second Hindi morning briefing | Facts computed in SQL -> `sarvam-105b` writes the script -> Sarvam Bulbul TTS speaks it (Soundbox-style player) |
| Ask by text or voice | Mic -> Sarvam Saaras STT -> LangGraph supervisor -> specialist agent -> tools -> reply (spoken back) |
| Six agents | Insights, Khata (udhaar), Inventory, Growth, Finance, Trust, each with LangChain tools |
| Human approval | Agents only *propose*. LangGraph `interrupt()` pauses until you tap Approve or say "Haan" |
| Udhaar recovery | Approved reminders land on the Customer Phone simulator with a Paytm pay link. Paying marks the udhaar recovered and ROI rises live |
| Stock-outs | Days-of-cover forecast; approved reorders create a purchase order and a distributor message |
| Expiring products | Batches expiring within 14 days with units and money at risk; approved clearance applies a tiered discount (never below cost) and messages recent customers |
| Win-back | Lapsed regulars found by SQL; approved cashback campaign goes live; simulate redemptions to see customers return |
| Finance | 7-day cash-flow forecast, indicative loan eligibility, GST summary by slab |
| Trust | Statistical fraud flags (unusual amount, rapid repeats), each with a reason |
| Agent trace | Routing, tool calls and the approval gate stream live into the UI (SSE) |
| ROI | "This week Munim recovered Rs X, prevented N stock-outs, brought back M customers" |

## Architecture

```
React + TS (Vite, Tailwind, Recharts, TanStack Query)
   |  REST + SSE
FastAPI  --  routers (HTTP only) -> services (all business logic) -> SQLAlchemy -> Neon Postgres
   |
LangGraph:  router -> {insights|khata|inventory|growth|finance|trust|general}
            -> request_approval -> await_decision (interrupt) -> finalize
   |  PostgresSaver checkpoints, async audit trail (agent_events)
Sarvam AI:  sarvam-105b (chat, tool calling, structured output) | Saaras (STT) | Bulbul (TTS)
```

Design rules that make it trustworthy:

- **Numbers never come from the LLM.** Services compute them in SQL/Python; the model routes, calls tools and explains.
- **The LLM cannot act.** `propose_*` tools only create *pending* actions. Execution happens after approval, idempotently.
- **Merchant isolation.** `merchant_id` comes from the signed JWT, never from model output. Text-to-SQL is AST-validated (sqlglot), view-scoped, `READ ONLY`, row-capped and has a statement timeout.
- **PII** (phone numbers) is masked before text reaches the LLM.
- **Money** is stored as integer paise.
- **Resilience.** Sarvam calls retry with backoff; if the model fails, agents fall back to deterministic tools so the demo never dead-ends.
- **Observability.** JSON logs with request IDs, `/health` and `/ready`, consistent `{error:{code,message,request_id}}` errors, persisted agent events.

## Run it

Prerequisites: Python 3.12, Node 20+. Copy `.env.example` to `.env` and fill in `SARVAM_API_KEY` and `DATABASE_URL` (a Postgres URL, e.g. Neon).

```powershell
./scripts/dev.ps1 setup      # venv + pip + npm install
./scripts/dev.ps1 seed       # create tables and synthetic Paytm data (takes ~2 min on a remote DB)
./scripts/dev.ps1 api        # http://localhost:8000  (docs at /docs)
./scripts/dev.ps1 web        # http://localhost:5173
./scripts/dev.ps1 test       # pytest
```

## Demo script (about 4 minutes)

1. **Login** as *Sharma General Store, Hinjawadi*. Home plays the Hindi **morning briefing** (press play). Point at the ROI banner.
2. **Stock alert.** On Home, approve *Reorder from Gupta Dairy*. Open *Customer Phone* to show the distributor message.
3. **Udhaar.** Approve *Send 3 udhaar reminders*. In *Customer Phone* open Ramesh Kulkarni's chat and tap **Pay with Paytm**. Pay. Return to Home: recovered amount rose live.
4. **Win-back.** Approve the cashback campaign, go to *Growth*, click **Simulate customers redeeming**. Customers won back rises.
5. **Ask by voice.** *Ask Munim*, press the mic, say "Diwali ke liye loan milega?" Watch the **agent trace** (supervisor -> Finance agent -> tool call) and hear the answer.
6. **Human in the loop.** Ask "Udhaar wapas kaise aayega? Reminder bhejo". The graph pauses with an approval card. Say or type "Haan" and watch it resume and execute.
7. Show *Finance*, *Trust* (planted fraud) and *Roadmap*. Use **Reset demo state** on Home to replay.

## Simulated today, real in production

WhatsApp (Customer Phone simulator + `wa.me` link), Paytm payment gateway (mock pay page), Soundbox hardware, distributor APIs, peer benchmark data and Paytm transaction feeds (synthetic data). See the in-app *Roadmap* page.

## Engineering notes

- Scoped for a hackathon: schema is created by the seed script (`create_all`) rather than Alembic migrations; no strict `mypy`, `slowapi`, shadcn or pre-commit hooks. The in-memory rate limiter is per-process.
- The Sarvam chat model is called through its OpenAI-compatible `/v2` endpoint (supports `reasoning_effort: none`, tool calling and structured output), wrapped by LangChain's `ChatOpenAI`.
- Tests: `pytest -m "not integration"` runs offline unit tests; integration tests run against the seeded database, and agent-graph tests use a stubbed (offline) LLM.
- Rotate the Sarvam key and database password you shared during development.
