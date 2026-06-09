#!/bin/bash
set -e
cd "$(dirname "$0")"

# Permanent public URL from named-tunnel setup (optional).
if [ -f "data/cloudflare-tunnel.env" ] && [ -z "$PUBLIC_URL" ]; then
  # shellcheck disable=SC1091
  source "data/cloudflare-tunnel.env"
  export PUBLIC_URL
fi

PORT="${PORT:-5050}"

# Stop anything already bound to this port; show maintenance page while updating
if lsof -ti :"$PORT" >/dev/null 2>&1; then
  echo "Stopping existing process on port $PORT..."
  lsof -ti :"$PORT" | xargs kill -9 2>/dev/null || true
  for _ in 1 2 3 4 5; do
    lsof -ti :"$PORT" >/dev/null 2>&1 || break
    sleep 1
  done
fi

MAINT_PID=""
stop_maintenance() {
  if [ -n "$MAINT_PID" ]; then
    kill "$MAINT_PID" 2>/dev/null || true
    wait "$MAINT_PID" 2>/dev/null || true
    MAINT_PID=""
  fi
}

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

if ! lsof -ti :"$PORT" >/dev/null 2>&1; then
  echo "Showing update message while server prepares..."
  .venv/bin/python3 scripts/serve_maintenance.py "$PORT" &
  MAINT_PID=$!
  trap stop_maintenance EXIT
  sleep 0.5
fi

.venv/bin/pip install -q gunicorn

stop_maintenance
trap - EXIT

if [ -x ".venv/bin/gunicorn" ]; then
  GUNICORN=".venv/bin/gunicorn"
elif command -v gunicorn >/dev/null 2>&1; then
  GUNICORN="gunicorn"
else
  echo "ERROR: gunicorn not found. Run: pip3 install gunicorn"
  exit 1
fi

export SECRET_KEY="${SECRET_KEY:-dev-change-me-in-production}"

echo ""
echo "Starting WC 2026 Predictions on port $PORT..."
echo "  Local:  http://localhost:$PORT"
echo ""
if [ -n "$PUBLIC_URL" ]; then
  echo "  Public: $PUBLIC_URL  (permanent — run ./share-persistent.sh in another terminal)"
else
  echo "To share with friends on the internet, open a SECOND terminal and run:"
  echo "  ./share-persistent.sh   (permanent URL on your domain — run ./setup-named-tunnel.sh once)"
  echo "  ./share.sh              (temporary trycloudflare.com URL)"
fi
echo ""

exec "$GUNICORN" -w 2 -b "0.0.0.0:$PORT" app:app
