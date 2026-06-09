#!/bin/bash
set -e
cd "$(dirname "$0")"

PORT="${PORT:-5050}"
BIN="./bin/cloudflared"

if [ ! -x "$BIN" ]; then
  echo "Downloading cloudflared (one-time)..."
  mkdir -p bin
  ARCH=$(uname -m)
  if [ "$ARCH" = "arm64" ]; then
    URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz"
  else
    URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz"
  fi
  curl -fsSL "$URL" -o /tmp/cloudflared.tgz
  tar -xzf /tmp/cloudflared.tgz -C bin cloudflared
  chmod +x "$BIN"
  rm /tmp/cloudflared.tgz
fi

if ! lsof -ti :"$PORT" >/dev/null 2>&1; then
  echo "ERROR: Nothing is running on port $PORT."
  echo "Start the app first in another terminal:  ./start.sh"
  exit 1
fi

echo ""
echo "Creating a public link (free, via Cloudflare)..."
echo "Keep this terminal open while friends use the app."
echo ""
echo "When you see a URL like https://xxxx.trycloudflare.com:"
echo "  1. Copy that URL"
echo "  2. Stop the server (Ctrl+C in the start.sh terminal)"
echo "  3. Restart with:  PUBLIC_URL=https://xxxx.trycloudflare.com ./start.sh"
echo "  4. Re-copy the invite link from the app — it will now use the public URL"
echo ""

# Use HTTP/2 when QUIC (port 7844) is blocked by firewall/router
exec "$BIN" tunnel --protocol http2 --url "http://localhost:$PORT"
