# FactMesh

A generalizable **Fact Knowledge Layer** that extracts atomic facts from PDFs, grounds every fact in source evidence (document + page + verbatim quote), and identifies cross-document relationships: corroboration, contradiction, and contextual differences.

Built for the Superjoin VIT 2026 Engineering Intern Assignment.

## Quick Start

See [Setup and Run Instructions](#setup-and-run-instructions) below.

## Setup and Run Instructions

> **Prerequisites**: Docker Desktop, Python 3.10+, Node.js 18+, an Anthropic API key.

```
# 1. Clone and enter the repo
git clone <repo-url>
cd factmesh

# 2. Copy and fill in environment variables
cp .env.example backend/.env
# Edit backend/.env and add your ANTHROPIC_API_KEY

# 3. Start PostgreSQL + pgvector
docker compose up -d

# 4. Set up the backend
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
cd ..

# 5. Set up the frontend
cd frontend
npm install
cd ..

# 6. Run the backend (from backend/)
cd backend
uvicorn app.main:app --reload --port 8000

# 7. Run the frontend (from frontend/, in a separate terminal)
cd frontend
npm run dev
```

## Video Demo

> _Link to ≤3-minute demo video (to be added after recording)._

## Approach

See [docs/architecture.md](docs/architecture.md) for detailed architecture, schema, and design decisions.

## Limitations and Next Steps

_To be completed after full end-to-end run._

## Additional Notes

_To be completed._
