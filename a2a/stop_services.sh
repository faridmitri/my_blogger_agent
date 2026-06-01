#!/usr/bin/env bash
# Stop all specialist A2A services started by run_services.sh
set -euo pipefail
if compgen -G ".logs/*.pid" > /dev/null; then
  for pidfile in .logs/*.pid; do
    pid=$(cat "$pidfile")
    if kill "$pid" 2>/dev/null; then
      echo "Stopped $(basename "$pidfile" .pid) (pid $pid)"
    fi
    rm -f "$pidfile"
  done
else
  echo "No running services found (.logs/*.pid missing)."
fi
