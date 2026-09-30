# SmartSOP - GMP Document Builder

A web application for generating GMP-compliant pharmaceutical documents with AI-assisted content. Built with Angular 18 (SSR) and Flask, it uses a local Ollama LLM to fill in procedure steps, equipment lists, references, and more.

## What it does

- **8 document templates** covering the full GMP record/procedure taxonomy:

  | Category | Templates |
  |----------|-----------|
  | Batch Records | Cell Processing Facility Batch Record |
  | Validations | Validation Protocol (IQ/OQ/PQ) |
  | Qualifications | Equipment Qualification Record |
  | Forms | Deviation/Nonconformance Form, Change Control Form |
  | Reports | Investigation Report, Annual Product Review (APR) |
  | Procedures | Standard Operating Procedure (SOP) |

- **AI content generation** per section (or "Fill all with AI" in parallel)
- **Paper scraping** from PubMed Central open-access literature to auto-fill equipment, materials, and procedure steps from published methods
- **Word document output** with exact pharmaceutical formatting (landscape/portrait, gray-shaded headers, step procedure tables, approval blocks, flowchart placeholders)
- **GMP procedure prefix conventions** baked into prompts: EQ- (Equipment), GN- (General), PR- (Processing), QA- (Quality Assurance), TM- (Test Method)

## Architecture

```
Browser (port 4200 dev / 4000 prod)
  |
  |  /api/*  ── proxy ──>  Flask backend (port 5001)
  |                            |
  |                            |── Ollama LLM (port 11434)
  |                            |── PubMed Central API
  |                            └── python-docx + OOXML
  |
Angular 18 SSR (Express)
```

## Prerequisites

- **Node.js** 20+ and npm
- **Python** 3.9+
- **Ollama** (for AI features) - [install instructions](https://ollama.com/download)

## Quick start (local development)

```bash
# 1. Clone and install
git clone https://github.com/avaarm/smartsop.git
cd smartsop
npm install
pip install -r requirements-gmp.txt

# 2. Start Ollama and pull a model
ollama serve &
ollama pull llama3

# 3. Start the Flask backend
python gmp_server.py

# 4. In a new terminal, start the Angular dev server
npm start

# 5. Open http://localhost:4200 and create your account.
#    The first registered user becomes the platform superadmin.
```

## Accounts & authentication

The app is multi-tenant: every document and training-data set belongs to an
**account** (an organization or facility), and users reach an account through a
**membership** (`owner` / `admin` / `member`).

- Visiting the app redirects to **`/login`**; users register or sign in there.
- The **first user to register becomes the superadmin** (can see every account).
  Registering with an organization name also creates that account and makes the
  user its owner.
- Auth is a short-lived **JWT** sent as `Authorization: Bearer <token>`. Set a
  strong **`JWT_SECRET`** in production — without it the server falls back to an
  insecure development key and logs a warning.
- Every account and document API requires a valid token and membership, so one
  organization can't read or modify another's data.

The Angular dev server proxies `/api` requests to `localhost:5001` (configured in `proxy.conf.json`).

> **Note:** Ollama is optional. The app works without it - you just won't have the "Fill with AI" and paper extraction features. Documents still generate with template defaults.

## Docker deployment

```bash
# Build and start all services (frontend + backend + Ollama)
docker compose up --build

# After Ollama starts, pull a model into the container
docker compose exec ollama ollama pull llama3
```

| Service | Port | Description |
|---------|------|-------------|
| `frontend` | 4000 | Angular SSR (production) |
| `backend` | 5001 | Flask + gunicorn |
| `ollama` | 11434 | Local LLM |

The frontend proxies `/api` to the backend container automatically via `API_URL` env var.

## Desktop app (macOS & Windows)

SmartSOP ships a native desktop client that connects to a SmartSOP **server** —
so workspaces, review/approval e-signatures and the shared audit trail stay
correct across everyone. It's a thin, secure Electron shell (no bundled backend,
no local database): on first launch it asks for your server address and opens the
web app in a dedicated window.

```bash
cd desktop
npm install
npm start            # opens the app; point it at your server (e.g. http://localhost:4000)
npm run dist:mac     # build a .dmg for macOS
npm run dist:win     # build a Setup .exe (run on Windows)
```

Tag a release (`git tag v1.0.0 && git push origin v1.0.0`) and
`.github/workflows/desktop-release.yml` builds the macOS **.dmg** and Windows
**.exe** on their own runners and attaches them to the GitHub Release. See
[`desktop/README.md`](desktop/README.md) for signing/notarization and config.

**Deploying the server** the desktop clients connect to: run the Docker stack
above on a host, set `JWT_SECRET` and `CORS_ORIGINS` (see `.env.example`), point
DNS at it, and give users that URL in the desktop app's connect screen.

## Project structure

```
smartsop/
├── src/                            # Angular frontend
│   ├── app/
│   │   ├── components/gmp-docs/    # Document builder UI
│   │   │   └── document-builder/   # Main 4-step builder component
│   │   └── services/
│   │       └── gmp-document.service.ts  # API client
│   └── main.ts
├── server.ts                       # Angular SSR Express server
├── ml_model/gmp/                   # Python GMP package
│   ├── templates/                  # JSON template definitions
│   │   ├── batch_record.json
│   │   ├── sop.json
│   │   ├── validation_protocol.json
│   │   ├── equipment_qualification.json
│   │   ├── deviation_form.json
│   │   ├── change_control_form.json
│   │   ├── investigation_report.json
│   │   └── annual_product_review.json
│   ├── template_schema.py          # Pydantic models for templates
│   ├── template_loader.py          # JSON template loader + cache
│   ├── word_engine.py              # DOCX generation (python-docx + OOXML)
│   ├── ooxml_helpers.py            # Low-level Word XML helpers
│   ├── ollama_service.py           # Ollama HTTP client
│   ├── prompts.py                  # LLM prompt templates per section type
│   ├── paper_scraper.py            # PubMed Central API client
│   ├── document_generator.py       # Orchestrator
│   └── routes.py                   # Flask blueprint
├── gmp_server.py                   # Flask entry point
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── requirements-gmp.txt            # Python deps (no torch/transformers)
└── .github/workflows/ci.yml        # GitHub Actions CI
```

## API endpoints

**Auth** (`/api/auth`):

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/register` | Create a user (+ optional account); returns a JWT |
| `POST` | `/login` | Exchange email/password for a JWT |
| `GET` | `/me` | Current user and their account memberships |

**GMP documents** (`/api/gmp`). `generate` and `preview` require a Bearer token:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/templates` | List all templates |
| `GET` | `/templates/:id` | Get template schema (sections, fields) |
| `POST` | `/generate` | Generate DOCX from template + data (auth) |
| `POST` | `/preview` | AI-generate a single section (auth) |
| `GET` | `/ollama/status` | Check Ollama availability |
| `GET` | `/papers/search?q=...&limit=10` | Search PubMed Central |
| `GET` | `/papers/:pmcid/methods` | Fetch paper methods section |
| `POST` | `/papers/autofill` | Extract GMP data from paper via LLM |
| `GET` | `/api/download/:filename` | Download generated DOCX |
| `GET` | `/health` | Backend health check |

**Accounts** (`/api/accounts`) — all routes require a Bearer token and
membership in the target account (superadmins may access any account).

## Adding a new template

1. Create a JSON file in `ml_model/gmp/templates/` following the schema of existing templates. Key fields:

   ```json
   {
     "id": "my_template",
     "name": "My New Template",
     "doc_type": "form",
     "orientation": "portrait",
     "sections": [
       {
         "id": "approval_block",
         "title": "APPROVED BY",
         "type": "approval_block",
         "required": true,
         "default_data": { ... }
       },
       {
         "id": "procedure",
         "title": "PROCEDURE",
         "type": "step_procedure",
         "llm_prompt": "Generate steps for {process_type} of {product_name}...",
         "step_config": { ... }
       }
     ]
   }
   ```

2. The `doc_type` determines the UI category grouping. Valid values: `batch_record`, `validation`, `qualification`, `form`, `report`, `sop`.

3. Available section types: `approval_block`, `references`, `attachments`, `general_instructions`, `step_procedure`, `equipment_list`, `materials_list`, `flowchart`, `checklist`, `comments`, `review`, `label_accountability`, `free_text`, `table`.

4. If you add a new `doc_type`, add it to the `DocumentType` enum in `ml_model/gmp/template_schema.py` and the `categoryOrder` array in `document-builder.component.ts`.

5. Templates are auto-discovered from the `templates/` directory - no registration needed.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET` | _(insecure dev key)_ | **Set this in production.** Signs auth tokens |
| `JWT_TTL_HOURS` | `168` | Token lifetime (hours) |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API URL |
| `API_URL` | `http://127.0.0.1:5001` | Backend URL (used by SSR proxy) |
| `CORS_ORIGINS` | `http://localhost:4200,http://127.0.0.1:4200` | Comma-separated allowed origins |
| `MAX_CONTENT_LENGTH` | `16777216` | Max request body size in bytes (16 MB) |
| `DATABASE_URL` | `sqlite:///smartsop.db` | SQLAlchemy database URL (use `postgresql://…` in prod) |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `10` / `20` | Per-worker DB connection pool (non-SQLite) |
| `AUTO_CREATE_TABLES` | `true` | Create tables on boot. Set `false` in prod and use migrations |
| `DOCUMENT_STORAGE` | `local` | `local` or `s3` |
| `S3_BUCKET` / `S3_PREFIX` / `S3_ENDPOINT_URL` | — | Object storage config when `DOCUMENT_STORAGE=s3` |
| `GENERATED_DOCS_DIR` | `./generated_docs` | Local storage directory |
| `GUNICORN_WORKERS` / `GUNICORN_THREADS` | `cpu_count` / `8` | Backend worker concurrency |
| `AUTH_RATELIMIT` / `LLM_RATELIMIT` | `10/min` / `30/min` | Per-IP limits on auth and LLM endpoints |
| `RATELIMIT_STORAGE_URI` | `memory://` | Set to `redis://…` for shared limits across instances |
| `CELERY_BROKER_URL` | — | Set (e.g. `redis://…`) to offload LLM calls to a worker |
| `CELERY_RESULT_BACKEND` | broker / sqlite | Where task results are stored |
| `PORT` | `4000` (web) / `5001` (api) | Service port |
| `FLASK_ENV` | `development` | Flask environment |

## Scaling to multiple instances

The backend is **stateless**, so it scales horizontally — run as many
instances behind a load balancer as you need. Three pieces of state must be
externalized (each is a single env var):

1. **Database** — point `DATABASE_URL` at Postgres
   (`postgresql://user:pass@host/db`). Connections are pooled and
   health-checked; `psycopg2-binary` ships in the image. SQLite (the default)
   is single-writer and only suitable for one instance.
2. **Generated documents** — set `DOCUMENT_STORAGE=s3` with `S3_BUCKET` so a
   file created on one instance is downloadable from any (served via presigned
   URLs). The local default pins files to one box. (`pip install boto3` for S3.)
3. **Auth** — already stateless (JWTs); just set the same `JWT_SECRET` on every
   instance.

Each instance serves concurrent requests with threaded gunicorn workers
(`gunicorn.conf.py`), so slow LLM calls don't block other users. Load balancers
should probe **`/health`** (liveness) and **`/ready`** (readiness — verifies the
database is reachable).

### Async LLM tasks

Section generation and paper autofill can each take 10-90s. Set
`CELERY_BROKER_URL` (e.g. `redis://redis:6379/0`) and run a Celery worker to
move them off the request path; the endpoints then enqueue a task and return a
`task_id` the client polls. Without a broker, tasks run inline (no Redis needed
for local dev). The frontend switches automatically based on `/api/gmp/config`.

```bash
# run a worker (production)
celery -A gmp_server:celery_app worker --loglevel=info --concurrency=4
```

`docker compose up` brings up the full stack — frontend, backend, **worker**,
Redis, Postgres, and Ollama — wired together.

## Database migrations

Schema changes are managed with Alembic (via Flask-Migrate). The zero-config
default still creates tables directly (`AUTO_CREATE_TABLES=true`); in production
set `AUTO_CREATE_TABLES=false` and let migrations own the schema:

```bash
export FLASK_APP=gmp_server.py
flask db upgrade                       # apply pending migrations

# after changing a model:
flask db migrate -m "describe change"  # autogenerate a migration
flask db upgrade                       # apply it
```

Adopting migrations on a database that was first created with
`AUTO_CREATE_TABLES=true`: stamp the baseline once, then upgrade —
`flask db stamp <initial-revision> && flask db upgrade`.

## CI/CD

GitHub Actions runs on every push/PR to `main`:
1. **Frontend** - TypeScript typecheck + production build
2. **Backend** - Template validation (all 8 templates) + DOCX smoke tests
3. **Docker** - Build both images

## Development tips

- **Frontend only**: `npm start` (port 4200, proxies API to 5001)
- **Backend only**: `python gmp_server.py` (port 5001, debug mode)
- **Build check**: `npx tsc --noEmit -p tsconfig.app.json`
- **Test templates**: `python -c "from ml_model.gmp.template_loader import TemplateLoader; [print(t) for t in TemplateLoader().list_templates()]"`
- **Generate test DOCX**: `python -c "from ml_model.gmp.document_generator import GMPDocumentGenerator; print(GMPDocumentGenerator().generate_document('sop', {'title':'Test','product_name':'X','process_type':'Y','description':'Z'})['filename'])"`

## License

MIT
