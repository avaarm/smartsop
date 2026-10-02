# Deploying the SmartSOP server

SmartSOP runs as a Docker stack (frontend + backend + worker + Postgres + Redis +
Ollama) behind **Caddy**, which gives you automatic HTTPS. Put it on one Linux
host — a cloud VM or an on-prem box — and the Mac/Windows desktop apps (and
browsers) connect to it at your domain.

## 1. Pick a host

Any Linux box with Docker works. Recommended sizing:

| | vCPU | RAM | Disk | Notes |
|---|---|---|---|---|
| **With AI assist (Ollama)** | 4 | 16 GB | 80 GB | Ollama is the heavy part; a GPU box is faster but not required. |
| **Without Ollama** | 2 | 4 GB | 40 GB | Set `WITHOUT_OLLAMA=1`; AI-assist features are simply unavailable. |

Good options: **DigitalOcean** or **Hetzner** (cheapest/fastest to start), **AWS
EC2 / GCP / Azure** (identical steps), or an **on-prem** server for data that must
stay in-house (common for GMP). Ubuntu 22.04/24.04 LTS is the easy default.

## 2. DNS

Point a hostname at the server's public IP:

```
A    sop.your-facility.com    ->    <server public IP>
```

## 3. Firewall

Open only **80** and **443** (and **22** for SSH). The app's internal ports
(4000/5001/11434) are bound to localhost and never exposed. On Ubuntu:

```bash
sudo ufw allow 22,80,443/tcp && sudo ufw enable
```

## 4. Deploy (one command)

```bash
# on the server
git clone https://github.com/avaarm/smartsop.git && cd smartsop

# with AI assist:
sudo DOMAIN=sop.your-facility.com ACME_EMAIL=you@your-facility.com ./deploy.sh

# or lean (no Ollama):
sudo DOMAIN=sop.your-facility.com WITHOUT_OLLAMA=1 ./deploy.sh
```

`deploy.sh` will:
1. Install Docker if it's missing (Ubuntu/Debian, as root).
2. Generate `.env` on first run — a random `JWT_SECRET`, your `DOMAIN`, and
   `CORS_ORIGINS=https://<domain>`.
3. Build and start the whole stack behind Caddy (automatic Let's Encrypt TLS).
4. Pull the Ollama model (unless `WITHOUT_OLLAMA=1`).

The first HTTPS request can take ~30s while Caddy issues the certificate. Then
open `https://sop.your-facility.com` — the first account you register becomes the
platform superadmin.

## 5. Connect the desktop app

Launch SmartSOP Desktop and enter `https://sop.your-facility.com` on the connect
screen (or **File → Connect to server…**). That's it.

## Operating it

```bash
# logs
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# update to the latest code (re-runs migrations automatically)
git pull && sudo DOMAIN=sop.your-facility.com ./deploy.sh

# stop / start
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# back up the database
docker compose exec db pg_dump -U smartsop smartsop > backup-$(date +%F).sql
```

### Notes

- **Secrets:** `.env` holds `JWT_SECRET` (chmod 600). Back it up; rotating it logs
  everyone out. Change the default Postgres password in `docker-compose.yml` for a
  real deployment.
- **Migrations** run automatically on each deploy (`flask db upgrade`), so the
  schema is always current; the app never uses `create_all` in production.
- **TLS** needs a real domain (Let's Encrypt won't issue for a bare IP). For a
  purely internal/air-gapped host, terminate TLS at your own proxy or use an
  internal CA and point `DOMAIN` at the internal hostname.
- **Scaling:** run the stack on a bigger box, or split Postgres/Redis/Ollama onto
  their own hosts via the env vars in `.env.example` (`DATABASE_URL`,
  `CELERY_BROKER_URL`, `OLLAMA_HOST`).
