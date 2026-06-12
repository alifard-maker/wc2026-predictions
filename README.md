# World Cup 2026 Predictions

A private online prediction league for FIFA World Cup 2026. Create a pool, share the invite link with friends (up to 100 players), and compete on the leaderboard.

## Features

- **72 group-stage fixtures** pre-loaded from the official schedule
- **Shareable invite link** — `/join/<code>`
- **Tagged predictions** — every pick is tied to your display name
- **Automatic scoring** — exact score = 5 pts, correct result = 2 pts, wrong = 0
- **Deadline enforcement** — predictions lock **1 hour** before kickoff
- **Live leaderboard** — updates when the admin enters results
- **Knockout rounds** — add matches later as teams are confirmed

## Quick start (local only)

```bash
cd wc2026-predictions
./start.sh
```

Open **http://localhost:5050**, create a pool.

## Share with friends on the internet

A `localhost` link **only works on your Mac**. Friends need a public URL.

### Permanent URL (recommended)

Use **your own domain** on Cloudflare so the link **never changes** after a Mac restart.

**One-time setup** (needs a free Cloudflare account + domain on Cloudflare DNS):

```bash
TUNNEL_HOSTNAME=wc.yourdomain.com ./setup-named-tunnel.sh
```

Follow the browser login, then every day:

**Terminal 1** — start the app:
```bash
./start.sh
```

**Terminal 2** — start the permanent tunnel:
```bash
./share-persistent.sh
```

Invite links use `https://wc.yourdomain.com` forever. Share that link once — no more broken URLs after reboots.

### Temporary URL (quick test)

**Terminal 1:** `./start.sh`  
**Terminal 2:** `./share.sh`

Copy the random `https://xxxx.trycloudflare.com` URL, restart with `PUBLIC_URL=... ./start.sh`. **This URL changes every restart** and cannot be recovered.

## How it works

1. **Create a pool** on the home page. You'll get an invite link and an admin secret — save the admin secret.
2. **Share the invite link** with friends. They pick a display name and join.
3. **Submit predictions** on the fixtures page before each deadline.
4. **Admin enters results** after matches finish — points recalculate for everyone automatically.

## Deploy online (permanent URL — recommended)

**Railway** — always-on hosting, fixed `*.up.railway.app` link, no laptop required.

See **[DEPLOY-RAILWAY.md](DEPLOY-RAILWAY.md)** for step-by-step setup (GitHub → Railway → volume → public domain).

Quick summary:
1. Push this repo to GitHub
2. Railway → Deploy from GitHub
3. Add variables: `SECRET_KEY`, `DATABASE_PATH=/data/predictions.db`
4. Add volume mounted at `/data`
5. Generate Railway domain → share invite links from the app

## Scoring

| Outcome | Points |
|---------|--------|
| Exact score | 5 |
| Correct win/draw, wrong score | 2 |
| Wrong result | 0 |

## Tech

- Python 3 + Flask
- SQLite (single file: `predictions.db`)
- No build step required
