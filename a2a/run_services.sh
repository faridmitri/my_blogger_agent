#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Local dev: start the three specialist A2A services.
#
# Each specialist runs as its own uvicorn process serving an A2A server with
# an agent card at /.well-known/agent-card.json. Once all three are up, run
# the orchestrator in a separate terminal with either:
#     adk web orchestrator          # interactive dev UI on :8000
#     python -m orchestrator.run    # headless one-shot
#
# Stop everything with: ./stop_services.sh  (or Ctrl-C this script)
# ─────────────────────────────────────────────────────────────
set -euo pipefail

mkdir -p .logs

start() {  # name  module  port
  local name="$1" module="$2" port="$3"
  echo "Starting ${name} on :${port} ..."
  PORT="${port}" uvicorn "${module}" --host 0.0.0.0 --port "${port}" \
      > ".logs/${name}.log" 2>&1 &
  echo $! > ".logs/${name}.pid"
}

start researcher agents.researcher_agent.agent:a2a_app 8001
start writer      agents.writer_agent.agent:a2a_app     8002
start publisher   agents.publisher_agent.agent:a2a_app  8003

sleep 6
echo
echo "Agent cards:"
for p in 8001 8002 8003; do
  echo "  http://localhost:${p}/.well-known/agent-card.json"
done
echo
echo "All specialists running. Logs in ./.logs/. Now run the orchestrator:"
echo "    adk web orchestrator        (UI on http://localhost:8000)"
echo "    python -m orchestrator.run  (headless)"
echo
echo "Press Ctrl-C to stop all services."

# Wait so Ctrl-C kills the backgrounded children.
trap 'echo; echo "Stopping..."; kill $(cat .logs/*.pid) 2>/dev/null || true; exit 0' INT TERM
wait
