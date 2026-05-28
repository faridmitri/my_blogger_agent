# Trend → Blog → Social Agent Pipeline

An autonomous content pipeline built on the [Google Agent Development Kit
(ADK)](https://google.github.io/adk-docs/). Once a day it discovers a timely
Google Cloud topic, writes an SEO-optimized blog post with a generated cover
image, publishes it to Blogger, cross-posts to a Facebook Page, and asks
Google to index the new URL.

- **Blog:** https://blog.cloud-edify.com
- **Runs:** daily at 09:00 America/Toronto via Cloud Scheduler → Cloud Run Job
- **Cost:** ~$0.10–0.15 per run

## Pipeline

The root agent is a `SequentialAgent` of six stages. Each stage reads from and
writes to shared session state.

| # | Stage | Type | Reads → Writes |
|---|-------|------|----------------|
| 1 | `researcher` | Sequential (Parallel + LLM) | candidates → `selected_trend` |
| 2 | `blog_writer` | LLM | `selected_trend` → `blog_draft` |
| 3 | `draft_splitter` | plain Python (no LLM) | `blog_draft` → `blog_draft_*` fields |
| 4 | `image_creator` | LLM + Imagen 4 | `blog_draft_image_prompt` → `cover_image_url` |
| 5 | `blogger_publisher` | LLM + Blogger API | draft fields → `published_url` |
| 6 | `facebook_poster` | LLM + Graph API | draft + URL → `facebook_post_url` |

After the agent loop, `run_agent.py` pings the Google Indexing API with
`published_url` (no LLM, no extra cost).

### Stage 1 — research sources

The researcher runs four discoverers in parallel, then a finalizer picks one
topic and dedups it against recent posts. Because this blog lives on a Google
Cloud domain, **Google Cloud sources are prioritized**; Reddit is a fallback
for engagement velocity.

| Discoverer | Source | Signal |
|------------|--------|--------|
| `tech_trends` | Reddit r/artificial (`fetch_rising_posts`) | upvote velocity |
| `gcp_news` | Google Cloud blog RSS (`fetch_feed_items`) | freshness |
| `gcp_releases` | Google Cloud release-notes feed | freshness |
| `gcp_learning` | Training & Certifications feed | freshness |

Feed URLs live in a small registry in `trend_agent/tools/feed_tool.py`. The
discoverers pass a short `feed_key` (e.g. `"gcp_blog"`), never a raw URL, so a
model typo can't redirect the fetcher.

## Project structure

```
run_agent.py                       Production entrypoint (headless)
trend_agent/
  agent.py                         Root SequentialAgent wiring
  prompts.py                       All agent instructions (tune here)
  sub_agents/
    researcher.py                  Parallel discovery + finalizer
    writer.py  draft_splitter.py
    image_creator.py  blogger_publisher.py  facebook_poster.py
  tools/
    reddit_tool.py                 Reddit rising posts
    feed_tool.py                   Google Cloud RSS/Atom feeds
    imagen_tool.py                 Imagen 4 → GCS upload
    blogger_tool.py                Blogger API v3 publish
    blogger_history_tool.py        Recent posts (dedup memory)
    facebook_tool.py               Graph API page post
    indexing_tool.py               Google Indexing API ping
tests/                             pytest units for pure-Python logic
.github/workflows/deploy.yml       CI/CD to Cloud Run Job
```

## Setup

Requires Python 3.13 (matches the Docker base image) and the gcloud CLI.

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                                # then fill in values
```

### Credentials

`BLOGGER_REFRESH_TOKEN` must be generated under the account that **owns the
blog** and must carry both the `blogger` and `indexing` OAuth scopes.
Generate it locally (the script is gitignored; install `google-auth-oauthlib`
separately, it is not a runtime dependency):

```bash
pip install google-auth-oauthlib
python get_refresh_token.py
```

The Indexing API does not use IAM roles — authorization comes from the OAuth
account being an **Owner** of the property in Google Search Console.

## Local development

```bash
adk web .            # interactive UI with per-stage inspection
python run_agent.py  # headless, exactly what runs in production
```

## Testing

```bash
python -m pytest tests/ -q
```

Tests cover the pure-Python logic that doesn't need ADK or network access:
feed parsing/filtering (`feed_tool`) and the writer-output JSON extraction
(`draft_splitter`). They stub `feedparser.parse` with fixtures, so they run
offline.

## Deployment

Pushing to `main` triggers `.github/workflows/deploy.yml`, which builds the
image, pushes to Artifact Registry, and updates the `trend-agent-job` Cloud
Run Job. Secrets are injected from Secret Manager at deploy time. A successful
run ends with:

```
✓ Stage complete: https://blog.cloud-edify.com/2026/05/...
✓ Stage complete: https://www.facebook.com/<page_id>/posts/<id>
↳ Requesting Google indexing for: https://blog.cloud-edify.com/2026/05/...
✓ Indexing ping sent — 2026-05-...Z
```

## Known limitations

- **Blogger search description.** `blogger_tool.py` sends `meta_description`
  via the post resource's `customMetaData` field. Blogger's API support for
  setting the search-description meta tag is unreliable; verify in the
  dashboard that descriptions actually appear, and that *Settings → Meta tags
  → Enable search description* is ON.
- **Custom permalink.** The publisher sets `permalink` to `/<slug>.html`.
  Blogger may ignore or reject permalinks that don't match its expected
  `/YYYY/MM/<slug>.html` shape; confirm slugs land as intended.
- **Feeds are "latest," not "trending."** The GCP feeds are chronological, so
  the finalizer ranks by freshness (`age_hours`), not popularity. The
  `max_age_hours` filter in `feed_tool.py` (default 72h) prevents re-surfacing
  stale items; pair it with the dedup step so the same release note isn't
  blogged twice.
