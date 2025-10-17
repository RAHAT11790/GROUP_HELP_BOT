# RS-GROUP-BOT (Flask uptime server)

Simple Flask server intended to be used with UptimeRobot to keep your bot or service alive when deployed on Render (or similar).

## Files
- `app.py` — Flask application with `/` and `/health` endpoints.
- `requirements.txt` — Python dependencies.
- `Dockerfile` — Container build file for Render or Docker hosts.
- `.gitignore` — Common ignores.

## Local run
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export PORT=5000
python app.py
```

## Docker (local)
```bash
docker build -t rs-group-bot .
docker run -p 5000:5000 rs-group-bot
```

## Deploy to Render
1. Create a GitHub repo named `RS-GROUP-BOT` and push these files.
2. On Render, click **New** → **Web Service** → Connect GitHub → Select the repo.
3. Choose **Docker** (Render will use the Dockerfile) and deploy.
4. After deploy, use `/health` endpoint for UptimeRobot monitoring.

## UptimeRobot
- Add a new monitor of type `HTTP(s)` pointing to `https://your-render-url/health`.
- Set check interval (e.g., 5 minutes).

That's it — your RS group uptime server will reply with JSON at `/health` and plain text at `/`.
