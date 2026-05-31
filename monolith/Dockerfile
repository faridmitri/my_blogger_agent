FROM python:3.13-slim

# Real-time logs in Cloud Run + no .pyc clutter
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements first — Docker caches this layer separately
# so pip install is skipped on rebuilds if requirements didn't change
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only what the agent needs — nothing else
COPY trend_agent/ ./trend_agent/
COPY run_agent.py .

CMD ["python", "run_agent.py"]