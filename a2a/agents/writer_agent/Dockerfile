FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Shared library + this specialist's package only.
COPY common/ ./common/
COPY agents/writer_agent/ ./agents/writer_agent/

ENV PORT=8002
CMD ["sh", "-c", "uvicorn agents.writer_agent.agent:a2a_app --host 0.0.0.0 --port ${PORT}"]
