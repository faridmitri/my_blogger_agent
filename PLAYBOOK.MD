# Playbook — Digital Worker Agent

Two architectures in one repo:

- **`monolith/`** — the **deployed production system**. A single ADK
  `SequentialAgent` that runs as a Cloud Run **Job**, triggered daily by Cloud
  Scheduler. This is what publishes the blog every day.
- **`a2a/`** — the **local / reference** Agent-to-Agent version. Same pipeline
  split into an orchestrator + three specialist services over the A2A protocol.
  Run it locally to explore the distributed design. It is **not** deployed.

This playbook covers: running each locally, and deploying the monolith.

Your GCP constants (already baked into the workflow):

```
PROJECT_ID      = YOUR PROJECT ID
REGION          = us-central1
ARTIFACT_REPO   = trend-agent
JOB_NAME        = trend-agent-job
SERVICE_ACCOUNT = YOUR SA

---

# PART A — Repo layout

```
DigitalCreatorAgent/
├── README.md
├── .github/workflows/
│   └── deploy-monolith.yml      ← the ONLY workflow; deployspowershell the monolith
├── monolith/                    ← DEPLOYED (Cloud Run Job)
│   ├── trend_agent/
│   ├── run_agent.py
│   ├── Dockerfile               ← python:3.12-slim
│   ├── requirements.txt
│   ├── tests/
│   └── .env.example
└── a2a/                         ← LOCAL / REFERENCE (not deployed)
    ├── orchestrator/
    ├── agents/{researcher,writer,publisher}_agent/
    ├── common/
    ├── tests/
    ├── Dockerfiles (kept for reference only)
```

The `.venv` lives at the **repo root** and is shared by both folders.

---

# PART B — Run the monolith locally (the deployed pipeline)

```powershell
cd D:\projects\DigitalCreatorAgent\monolith
..\.venv\Scripts\activate          # venv is at the repo root
pip install -r requirements.txt
copy .env.example .env             # then fill in the 12 values
python run_agent.py
```

`run_agent.py` runs the whole chain in one process: research → write → image →
Blogger → Facebook → indexing ping. This is exactly what the Cloud Run Job runs.

Run its tests:

```powershell
python -m pytest tests/ -q
```

---

# PART C — Run the A2A version locally (reference)

The A2A version is three services + an orchestrator. All on localhost, no auth.

```powershell
cd D:\projects\DigitalCreatorAgent\a2a
..\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env             # same 12 values; leave USE_CLOUD_RUN_AUTH=false
python -m pytest tests/ -q          # 14 offline tests
```

Start the three specialist services, each in its own terminal:

```powershell
# Terminal 1 — researcher
uvicorn agents.researcher_agent.agent:a2a_app --host 127.0.0.1 --port 8001
# Terminal 2 — writer
uvicorn agents.writer_agent.agent:a2a_app --host 127.0.0.1 --port 8002
# Terminal 3 — publisher
uvicorn agents.publisher_agent.agent:a2a_app --host 127.0.0.1 --port 8003
```

Confirm a card is served:

```powershell
python -c "import urllib.request,json; print(json.load(urllib.request.urlopen('http://127.0.0.1:8001/.well-known/agent-card.json'))['name'])"
```

Run the orchestrator (Terminal 4):

```powershell
python -m orchestrator.run
```

Or test one specialist in isolation (read-only, safe):

```powershell
python a2a_client_example.py http://127.0.0.1:8001 "Find today's best Google Cloud blog topic."
```

> ⚠️ The full orchestrator run **publishes for real** (Blogger + Facebook).
> To test posting without the pipeline: `python test_facebook.py "<a-real-blog-url>"`.

The A2A Dockerfiles and the ID-token auth in
`orchestrator/remote_agent_connection.py` (gated by `USE_CLOUD_RUN_AUTH`) are
present for reference — they show how A2A *would* deploy — but no workflow
builds them.

---

# PART D — One-time GCP setup (for monolith deployment)

Most of this you likely already did for the original project; verify each.

### D1. Enable APIs

```bash
gcloud config set project gen-lang-client-0230396996
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudscheduler.googleapis.com \
  aiplatform.googleapis.com \
  iamcredentials.googleapis.com
```

### D2. Artifact Registry repo (named `trend-agent`)

```bash
gcloud artifacts repositories describe trend-agent --location=us-central1 \
  || gcloud artifacts repositories create trend-agent \
       --repository-format=docker --location=us-central1 \
       --description="DigitalCreatorAgent images"
```

### D3. The 12 secrets in Secret Manager

Create each once (repeat for all 12 names):

```bash
printf "YOUR_VALUE" | gcloud secrets create GOOGLE_CLOUD_PROJECT --data-file=- \
  || printf "YOUR_VALUE" | gcloud secrets versions add GOOGLE_CLOUD_PROJECT --data-file=-
```

Names: `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GOOGLE_GENAI_USE_VERTEXAI`,
`VERTEX_IMAGEN_LOCATION`, `IMAGE_BUCKET`, `BLOGGER_CLIENT_ID`,
`BLOGGER_CLIENT_SECRET`, `BLOGGER_REFRESH_TOKEN`, `BLOGGER_BLOG_ID`,
`FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_ACCESS_TOKEN`, `FACEBOOK_API_VERSION`.

### D4. Service account roles

```bash
SA=YOUR SA
PROJECT=YOUR PROJECT ID
for ROLE in \
  roles/secretmanager.secretAccessor \
  roles/aiplatform.user \
  roles/storage.objectAdmin \
  roles/artifactregistry.writer \
  roles/run.admin \
  roles/iam.serviceAccountUser ; do
  gcloud projects add-iam-policy-binding $PROJECT \
    --member="serviceAccount:$SA" --role="$ROLE"
done
```

### D5. Workload Identity Federation (GitHub → GCP, no keys)

If your original CI already used WIF, this is done. Otherwise:

```bash
gcloud iam workload-identity-pools create github-pool \
  --location=global --display-name="GitHub pool" || true
gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location=global --workload-identity-pool=github-pool \
  --display-name="GitHub provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com" || true

# Allow YOUR repo to impersonate the SA. Replace OWNER/REPO.
PROJECT_NUM=487905766954
gcloud iam service-accounts add-iam-policy-binding \
  trend-agent-runner@gen-lang-client-0230396996.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUM}/locations/global/workloadIdentityPools/github-pool/attribute.repository/OWNER/REPO"
```

---

# PART E — Deploy the monolith (CI/CD)

Deployment is automatic. The workflow `.github/workflows/deploy-monolith.yml`
is **path-filtered to `monolith/**`** — only changes under `monolith/` trigger
a deploy. Editing `a2a/` deploys nothing.

```bash
git add monolith/
git commit -m "Update monolith"
git push origin main
```

The workflow then:
1. Authenticates via Workload Identity Federation.
2. Builds the image from `monolith/Dockerfile` (build context = `monolith/`).
3. Pushes to Artifact Registry.
4. Creates or updates the Cloud Run **Job** `trend-agent-job` with the 12
   secrets injected as env vars.

Watch it under the repo's **Actions** tab → "Deploy Monolith to Cloud Run".

Verify:

```bash
gcloud run jobs list --region=us-central1     # expect: trend-agent-job
```

---

# PART F — Run and schedule the job

### F1. Trigger one run manually

```bash
gcloud run jobs execute trend-agent-job --region=us-central1
```

### F2. Watch logs

```bash
gcloud beta run jobs executions list --job=trend-agent-job --region=us-central1
gcloud beta run jobs executions logs <EXECUTION_NAME> --region=us-central1
```

Success: a topic is picked, a post is written, an image is generated, the post
goes live on Blogger, a Facebook post is created, and the indexing ping is sent.

### F3. Schedule it daily (09:00 America/Toronto)

```bash
PROJECT=gen-lang-client-0230396996
gcloud scheduler jobs create http trend-agent-daily \
  --location=us-central1 \
  --schedule="0 9 * * *" \
  --time-zone="America/Toronto" \
  --uri="https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/trend-agent-job:run" \
  --http-method=POST \
  --oauth-service-account-email=trend-agent-runner@${PROJECT}.iam.gserviceaccount.com
```

The Job runs once and exits each day. Cloud Run Jobs don't stay running, so you
pay only for the ~2-4 minutes per execution.

---

# PART G — Deploy the A2A version (optional)

The A2A architecture ships with `.github/workflows/deploy-a2a.yml`. It is
**manual-only by default** — a normal `git push` only ever deploys the monolith.
To deploy A2A, you explicitly trigger it from the Actions tab.

### G1. Deploy via GitHub Actions (recommended)

1. GitHub → **Actions** → **Deploy A2A to Cloud Run**
2. **Run workflow**, type `deploy` in the confirm box, click **Run workflow**

It builds four images in parallel, deploys the three specialist Cloud Run
**Services** (`--no-allow-unauthenticated`, scale-to-zero), wires each service
URL into the orchestrator's environment, grants the orchestrator SA
`roles/run.invoker` on each specialist, and deploys the orchestrator Cloud Run
**Job** with `USE_CLOUD_RUN_AUTH=true`. The final summary step prints the
`gcloud scheduler` command with your URLs filled in.

Prerequisites are the same as the monolith (Part D): APIs, Artifact Registry
(repo named `digital-worker`), the 12 secrets, Workload Identity Federation,
and service account roles.

### G2. Enable auto-deploy on push (optional)

To make A2A auto-deploy on push (if you're maintaining only A2A, or want both
architectures auto-deploying):

1. Open `.github/workflows/deploy-a2a.yml`
2. Uncomment the `push:` block
3. Optionally comment out or remove `workflow_dispatch`

The comment block at the top of that file explains this in detail.

> ⚠️ If both workflows have `push:` triggers, both deploy on every relevant
> push — the monolith on `monolith/**` changes, A2A on `a2a/**` changes.
> Enable this only intentionally.

### G3. Trigger and schedule the orchestrator job

```bash
# Manual test run:
gcloud run jobs execute trend-orchestrator-job --region=us-central1

# Schedule daily (copy the command from the workflow summary, or run this):
PROJECT=YOUR PROJECT ID
gcloud scheduler jobs create http trend-orchestrator-daily \
  --location=us-central1 --schedule="0 9 * * *" --time-zone="America/Toronto" \
  --uri="https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/trend-orchestrator-job:run" \
  --http-method=POST \
  --oauth-service-account-email=trend-agent-runner@${PROJECT}.iam.gserviceaccount.com
```

### G4. Scale-to-zero cost note

The three specialist services scale to zero when idle — no charge between runs.
They cold-start (a few seconds) when the orchestrator calls them, then scale
back down. You do NOT manually start or stop them; Cloud Run handles it.

> ⚠️ If you schedule both the monolith job AND the A2A orchestrator job, you
> get two posts per day. deploy and Schedule only one

---

# Daily workflow from now on

```powershell
# develop / test the deployed pipeline locally:
cd monolith ; ..\.venv\Scripts\activate
python -m pytest tests/ -q
python run_agent.py                  # optional full local run (publishes!)
git add monolith/ ; git commit -m "..." ; git push   # CI redeploys the Job

# explore the A2A version locally (never deploys):
cd ..\a2a ; ..\.venv\Scripts\activate
# start 3 services + python -m orchestrator.run
```

- Changes under `monolith/**` → auto build + deploy to Cloud Run.
- Changes under `a2a/**` → nothing deploys (local/reference only).

---

# Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| CI auth step fails | WIF binding missing for your repo | Re-run D5 with correct OWNER/REPO |
| `denied: permission` on docker push | SA lacks Artifact Registry writer | Re-run D4 |
| Secret not found at runtime | Secret name mismatch / not created | Re-check D3 names |
| Imagen permission denied | SA lacks aiplatform.user | Re-run D4 |
| Facebook `code 1` error | Odd characters in caption | The server sanitizes + retries; if it persists, re-check the Page token |
| A2A orchestrator stops after one step (local) | Specialist service down | Confirm all three uvicorn services are running |
