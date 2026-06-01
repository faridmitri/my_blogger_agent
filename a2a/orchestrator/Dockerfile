FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The orchestrator needs common/ (for prompts + model constants) and its own package.
COPY common/ ./common/
COPY orchestrator/ ./orchestrator/

# Headless one-shot run. The three specialist service URLs are injected as
# RESEARCHER_AGENT_URL / WRITER_AGENT_URL / PUBLISHER_AGENT_URL.
CMD ["python", "-m", "orchestrator.run"]
