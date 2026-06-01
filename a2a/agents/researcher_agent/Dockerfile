FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Shared library + this specialist's package only.
COPY common/ ./common/
COPY agents/researcher_agent/ ./agents/researcher_agent/

# Cloud Run injects $PORT. to_a2a's AgentCard reads RESEARCHER_PUBLIC_URL.
ENV PORT=8001
CMD ["sh", "-c", "uvicorn agents.researcher_agent.agent:a2a_app --host 0.0.0.0 --port ${PORT}"]
