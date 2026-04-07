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

# 5. Open http://localhost:4200
```

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

All routes are prefixed with `/api/gmp`.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/templates` | List all templates |
| `GET` | `/templates/:id` | Get template schema (sections, fields) |
| `POST` | `/generate` | Generate DOCX from template + data |
| `POST` | `/preview` | AI-generate a single section |
| `GET` | `/ollama/status` | Check Ollama availability |
| `GET` | `/papers/search?q=...&limit=10` | Search PubMed Central |
| `GET` | `/papers/:pmcid/methods` | Fetch paper methods section |
| `POST` | `/papers/autofill` | Extract GMP data from paper via LLM |
| `GET` | `/api/download/:filename` | Download generated DOCX |
| `GET` | `/health` | Backend health check |

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
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API URL |
| `API_URL` | `http://localhost:5001` | Backend URL (used by SSR proxy) |
| `PORT` | `4000` | Frontend SSR port |
| `FLASK_ENV` | `development` | Flask environment |

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
