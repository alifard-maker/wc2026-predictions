#!/bin/bash
# Share on your home Wi-Fi only (friends must be on the same network)
cd "$(dirname "$0")"
PORT="${PORT:-5050}"

IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
if [ -z "$IP" ]; then
  echo "Could not detect your local IP. Make sure you're on Wi-Fi."
  exit 1
fi

URL="http://${IP}:${PORT}"
echo ""
echo "Same-WiFi link: $URL"
echo ""
echo "Restart the app with:"
echo "  PUBLIC_URL=$URL ./start.sh"
echo ""
echo "Note: this only works for people on your home network, not the internet."
