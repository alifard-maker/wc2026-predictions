#!/bin/bash
# Run the permanent Cloudflare named tunnel (use after setup-named-tunnel.sh).
set -e
cd "$(dirname "$0")"

PORT="${PORT:-5050}"
BIN="./bin/cloudflared"
CONFIG_PATH="data/cloudflare-tunnel.yml"
ENV_PATH="data/cloudflare-tunnel.env"

if [ ! -x "$BIN" ]; then
  echo "ERROR: cloudflared not found. Run ./share.sh once to download it."
  exit 1
fi

if [ ! -f "$CONFIG_PATH" ]; then
  echo "ERROR: No named tunnel config at $CONFIG_PATH"
  echo "Run the one-time setup first:"
  echo "  TUNNEL_HOSTNAME=wc.yourdomain.com ./setup-named-tunnel.sh"
  exit 1
fi

if ! lsof -ti :"$PORT" >/dev/null 2>&1; then
  echo "ERROR: Nothing is running on port $PORT."
  echo "Start the app first:  ./start.sh"
  exit 1
fi

if [ -f "$ENV_PATH" ]; then
  # shellcheck disable=SC1090
  source "$ENV_PATH"
fi

echo ""
echo "Starting permanent tunnel..."
if [ -n "$PUBLIC_URL" ]; then
  echo "  Public URL: $PUBLIC_URL"
fi
echo "  Local app:  http://localhost:$PORT"
echo ""
echo "Keep this terminal open while friends use the pool."
echo "This URL does not change when you restart your Mac."
echo ""

exec "$BIN" tunnel --config "$CONFIG_PATH" run
