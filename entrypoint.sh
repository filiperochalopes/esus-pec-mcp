#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$ROOT/mcp-server/src:$ROOT/mcp-client"

UI_PORT="${UI_PORT:-8001}"
UI_HOST="${UI_HOST:-0.0.0.0}"
MCP_CMD="${MCP_CMD:-python -m pec_mcp.server}"
export MCP_HTTP_PORT="${MCP_HTTP_PORT:-5174}"
export MCP_HTTP_HOST="${MCP_HTTP_HOST:-127.0.0.1}"
# Também alinhar com o esquema de env do FastMCP (FASTMCP_HOST/PORT)
export FASTMCP_HOST="${FASTMCP_HOST:-$MCP_HTTP_HOST}"
export FASTMCP_PORT="${FASTMCP_PORT:-$MCP_HTTP_PORT}"

echo "==> Iniciando servidor MCP em http://${MCP_HTTP_HOST}:${MCP_HTTP_PORT} ..."
cd "$ROOT"
$MCP_CMD &
MCP_PID=$!

echo "==> Iniciando UI FastAPI em http://${UI_HOST}:${UI_PORT}"
uvicorn main:app --host "$UI_HOST" --port "$UI_PORT" --app-dir "$ROOT/mcp-client" &
UI_PID=$!

cleanup() {
  echo "Encerrando processos..."
  kill "$MCP_PID" "$UI_PID" >/dev/null 2>&1 || true
}

trap cleanup INT TERM

wait_for_any() {
  while true; do
    for pid in "$@"; do
      if ! kill -0 "$pid" >/dev/null 2>&1; then
        wait "$pid"
        return $?
      fi
    done
    sleep 1
  done
}

EXIT_CODE=0
wait_for_any "$MCP_PID" "$UI_PID" || EXIT_CODE=$?
cleanup
exit "$EXIT_CODE"
