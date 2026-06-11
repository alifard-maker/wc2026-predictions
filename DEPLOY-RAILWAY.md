# Deploy to Railway (permanent URL)

Host the pool on Railway so friends always use the same link — no laptop, no tunnels.

You get a stable URL like `https://wc2026-predictions-production.up.railway.app`.

## 1. Push code to GitHub

```bash
cd ~/wc2026-predictions
git add .
git commit -m "Prepare WC 2026 predictions for Railway"
```

Create a new **private** repo on [github.com/new](https://github.com/new), then:

```bash
git remote add origin git@github.com:YOUR_USER/wc2026-predictions.git
git push -u origin main
```

## 2. Create the Railway project

1. Sign up at [railway.com](https://railway.com) (GitHub login is easiest).
2. **New Project** → **Deploy from GitHub repo** → select `wc2026-predictions`.
3. Railway detects Python automatically (`Procfile` + `requirements.txt`).

## 3. Environment variables

In Railway → your service → **Variables**, add:

| Variable | Value |
|----------|--------|
| `SECRET_KEY` | Long random string (e.g. `openssl rand -hex 32`) |
| `DATABASE_PATH` | `/data/predictions.db` |
| `FOOTBALL_DATA_API_TOKEN` | Free API token from [football-data.org](https://www.football-data.org/client/register) — enables automatic live scores every 30s |

Do **not** set `PUBLIC_URL` — invite links use the Railway hostname automatically.

## 4. Persistent database (important)

Without a volume, pool data is wiped on every redeploy.

1. Railway → your service → **Volumes** → **Add volume**
2. Mount path: `/data`
3. Redeploy if prompted.

## 5. Generate a public URL

1. Service → **Settings** → **Networking** → **Generate domain**
2. Copy the `*.up.railway.app` URL — this is permanent for the project.

Share invite links from the app **Guide** page; they will use that domain.

## 6. (Optional) Move your existing pool from your Mac

If you already have friends in a local pool:

```bash
# After first deploy + volume are ready, copy your local DB into the volume:
railway login
railway link
railway run -- sh -c 'cat > /data/predictions.db' < predictions.db
```

Or start fresh on Railway and send friends the new invite link.

## 7. Updates

Push to GitHub → Railway redeploys automatically. Data stays on the volume.

## Cost

Railway’s hobby plan includes a monthly usage credit. This small Flask app typically fits within free/low-cost usage; check [railway.com/pricing](https://railway.com/pricing).

## Local vs Railway

| | Laptop + tunnel | Railway |
|--|-----------------|---------|
| URL changes on restart | Yes (quick tunnels) | No |
| Mac must stay on | Yes | No |
| Pool data | `predictions.db` locally | `/data/predictions.db` on volume |
