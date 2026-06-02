# 🤖 Digital Worker Agent

> An autonomous AI content engine that researches trending technology, writes SEO-optimized articles, generates cover art, and publishes to Blogger and Facebook — every day, with zero human input.

<p align="center">
  <img alt="Google ADK" src="https://img.shields.io/badge/Google_ADK-1.34-34A853?style=for-the-badge&logo=google&logoColor=white">
  <img alt="Gemini 2.5" src="https://img.shields.io/badge/Gemini-2.5_Flash-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white">
  <img alt="Imagen 4" src="https://img.shields.io/badge/Imagen-4-EA4335?style=for-the-badge&logo=google&logoColor=white">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-3_servers-FF6F00?style=for-the-badge">
  <img alt="A2A Protocol" src="https://img.shields.io/badge/A2A-Protocol-1A73E8?style=for-the-badge">
</p>

<p align="center">
  <img alt="Cloud Run" src="https://img.shields.io/badge/Cloud_Run-Service_%2B_Job-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="CI/CD" src="https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white">
  <img alt="Architectures" src="https://img.shields.io/badge/Architectures-Monolith_%2B_A2A-9334E6?style=for-the-badge">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-555555?style=for-the-badge">
</p>

---

## ✨ Why this repo is interesting

This is **one production pipeline, implemented two ways** — a rare side-by-side study of the same real workload as a **monolith** and as a **distributed multi-agent system**. Both ship complete, tested, and deploy to Cloud Run with full CI/CD. You can run either locally in minutes and read the exact same business logic expressed in two architectural styles.

It's a working reference for the questions every agent team eventually asks:

- When is a single `SequentialAgent` enough, and when do you split into services?
- How does shared session state differ from passing JSON across an A2A boundary?
- How do you wire agent-to-agent auth, agent cards, and orchestration *correctly*?

The answer lives in code you can run, not slides.

---

## 🎯 What it does

Every day, automatically, the agent:

| # | Stage | How |
|---|-------|-----|
| 1 | **Discovers** a timely Google Cloud topic | Parallel scan of 4 feeds + Google News, deduped against post history |
| 2 | **Writes** a 1,000–2,000 word SEO article | Gemini 2.5 Flash with a validated `BlogDraft` schema |
| 3 | **Generates** a cover image | Imagen 4 → Cloud Storage |
| 4 | **Publishes** to Blogger | Blogger API v3, content-safety gated |
| 5 | **Cross-posts** to Facebook | Caption + link card, Graph API |
| 6 | **Requests indexing** | Google Indexing API ping for fast recrawl |

Live example: a daily-updated tech blog, fully operated by this agent.

---

## 🏛️ The two architectures

### `monolith/` — one process, one deployable

<p align="center">
  <img src="img/monolith_architecture.png" alt="Monolith architecture" width="100%">
</p>

Five sub-agents run in sequence inside a single Python process. Data flows through **shared session state** — no network hops, no serialization. One Docker image, one Cloud Run **Job**, one thing to monitor. This is the deployed default and the right choice for a fixed daily job.

**Stack:** ADK `SequentialAgent` + `ParallelAgent` · MCP (3 stdio servers) · Gemini 2.5 Flash · Imagen 4 · Blogger v3 · Facebook Graph · GCS · Indexing API.

### `a2a/` — four services, Agent-to-Agent protocol

<p align="center">
  <img src="img/a2a_architecture.png" alt="A2A architecture" width="100%">
</p>

The same five stages, regrouped into **three independent specialist services** coordinated by an **orchestrator**. Each specialist is its own Cloud Run Service that publishes an **Agent Card** and speaks the **A2A protocol**. The orchestrator is an `LlmAgent` whose only tool is `send_message(agent_name, task)` — it keeps control across all three delegations, feeding each result into the next call (the "agent-as-a-tool" pattern, not sub-agent transfer).

**Stack:** ADK `LlmAgent` + `to_a2a` + `AgentCard` + `RemoteAgentConnections` · A2A JSON-RPC · the *same* MCP servers, models, and APIs.

---

## ⚖️ Monolith vs A2A at a glance

| | `monolith/` | `a2a/` |
|---|---|---|
| **Shape** | 1 `SequentialAgent`, 5 sub-agents | Orchestrator + 3 specialist services |
| **Data between stages** | Shared session state | JSON over the A2A network boundary |
| **Deployables** | 1 Cloud Run Job | 3 Cloud Run Services + 1 Job |
| **CI/CD trigger** | Auto on push to `monolith/**` | Manual by default; auto-on-push opt-in |
| **Service-to-service auth** | N/A (one process) | Google ID token (`USE_CLOUD_RUN_AUTH`) |
| **Scale-to-zero** | Job exits when done | Services idle at zero between runs |
| **Idle cost** | ~$0 | ~$0 |
| **Operational complexity** | Low | Higher (4 services, cards, auth) |
| **Best for** | A fixed daily autonomous job | Reusable agents, dynamic routing, teams |

---

## 🧩 Shared components

Both architectures reuse the **exact same** integration and tool code:

- **`feed_server.py`** — GCP blog, release notes, training, Google News *(MCP)*
- **`blogger_server.py`** — `list_recent_posts` (dedup) + `publish_post` *(MCP)*
- **`facebook_server.py`** — `post_to_page` with caption sanitize + retry *(MCP)*
- **`imagen_tool.py`** — Imagen 4 cover image → GCS
- **`indexing_tool.py`** — Google Indexing API ping
- **`BlogDraft`** — Pydantic schema validating the writer's output
- **`policy_gate`** — content-safety callback on every publish action
- **12 GCP secrets** — same Secret Manager names, injected into whichever runs

---

## 🚀 Quick start

```bash
git clone https://github.com/faridmitri/DigitalCreatorAgent.git
cd DigitalCreatorAgent
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
```

### Run the monolith locally

```bash
cd monolith
pip install -r requirements.txt
cp .env.example .env               # fill in the 12 values
python run_agent.py                # ⚠ publishes for real — run when ready
```

### Run the A2A version locally

```bash
cd a2a
pip install -r requirements.txt
cp .env.example .env               # same 12 values; keep USE_CLOUD_RUN_AUTH=false

# Terminals 1–3, one per specialist service:
uvicorn agents.researcher_agent.agent:a2a_app --host 127.0.0.1 --port 8001
uvicorn agents.writer_agent.agent:a2a_app     --host 127.0.0.1 --port 8002
uvicorn agents.publisher_agent.agent:a2a_app  --host 127.0.0.1 --port 8003

# Terminal 4 — drive the pipeline:
python -m orchestrator.run
```

Run the offline test suites any time (no network, no publishing):

```bash
cd monolith && pytest tests/ -q
cd a2a       && pytest tests/ -q
```

---

## ☁️ Deploying to Cloud Run

Both architectures ship with complete GitHub Actions CI/CD. See **`PLAYBOOK.MD`** for one-time GCP setup (APIs, Artifact Registry, the 12 secrets, Workload Identity Federation, IAM roles).

### Monolith — automatic on push

`deploy-monolith.yml` fires on every push to `main` touching `monolith/**`: it builds the image, pushes to Artifact Registry, and creates/updates the Cloud Run **Job**.

```bash
git add monolith/ && git commit -m "your change" && git push origin main
```

### A2A — manual from the Actions tab

`deploy-a2a.yml` is `workflow_dispatch`-only by default — it never fires on push, so a routine push only ever deploys the monolith.

1. **GitHub → Actions → "Deploy A2A to Cloud Run"**
2. **Run workflow** → type `deploy` to confirm.

It builds all four images, deploys the three Services (`--no-allow-unauthenticated`, scale-to-zero), grants the orchestrator `roles/run.invoker` on each, and deploys the orchestrator **Job** with `USE_CLOUD_RUN_AUTH=true`.

> **Want A2A to auto-deploy too?** Uncomment the `push:` block at the top of `deploy-a2a.yml` (the file documents exactly what to change). If both workflows auto-deploy *and* both jobs are scheduled, the blog publishes twice daily — enable intentionally.

### CI/CD summary

| Workflow | Trigger | Deploys |
|---|---|---|
| `deploy-monolith.yml` | Auto — push to `main`, paths `monolith/**` | Cloud Run **Job** |
| `deploy-a2a.yml` | Manual — `workflow_dispatch` (auto-on-push opt-in) | 3 Cloud Run **Services** + 1 **Job** |

---

## 🔐 How A2A services authenticate on Cloud Run

The three specialist services deploy `--no-allow-unauthenticated`. The orchestrator calls them with a **Google ID token** whose audience is each service's URL, handled automatically by `_GoogleIdTokenAuth` in `orchestrator/remote_agent_connection.py` when `USE_CLOUD_RUN_AUTH=true` (set by CI on the orchestrator job). Locally the flag defaults to `false` — plain HTTP, no tokens.

---

## 📁 Repo layout

```
DigitalCreatorAgent/
├── README.MD                       ← you are here
├── PLAYBOOK.MD                     ← step-by-step: local run, GCP setup, deploy
├── img/                            ← architecture + log screenshots
├── .github/workflows/
│   ├── deploy-monolith.yml         ← auto on push (monolith/**)
│   └── deploy-a2a.yml              ← manual; auto-on-push opt-in
│
├── monolith/                       ← THE DEPLOYED SYSTEM
│   ├── trend_agent/                ← ADK agent package (5 sub-agents, MCP, tools)
│   ├── run_agent.py                ← entrypoint
│   ├── Dockerfile · requirements.txt · tests/ · .env.example
│
└── a2a/                            ← DISTRIBUTED REFERENCE · ALSO DEPLOYABLE
    ├── orchestrator/               ← LlmAgent + send_message tool + auth
    ├── agents/
    │   ├── researcher_agent/       ← parallel discovery + finalizer
    │   ├── writer_agent/           ← BlogDraft schema + SEO writer
    │   └── publisher_agent/        ← image → blogger → facebook → indexing
    ├── common/                     ← shared prompts, MCP servers, tools, callbacks
    ├── tests/ · .env.example · requirements.txt
```

---

## 📸 Agents in action

| Monolith | A2A |
|---|---|
| ![Monolith logs](img/logs_monolith.png) | ![A2A logs](img/logs_a2a.png) |

---

## 📚 Further reading

- **`PLAYBOOK.MD`** — every command: run locally, one-time GCP setup, deploy each architecture, schedule the daily job, and troubleshoot.

---

<p align="center"><sub>Built with Google ADK · Gemini 2.5 · Imagen 4 · MCP · A2A · Cloud Run · Secret Manager · Artifact Registry · Blogger v3 · Facebook Graph · Google Indexing API</sub></p>