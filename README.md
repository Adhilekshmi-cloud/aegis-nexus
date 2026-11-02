# Aegis Knowledge Ingestion Challenge

This project delivers a production-style evidence-grounded knowledge ingestion and Q&A system for the Aegis Series-7 Hydraulic Control System dataset.

## Included capabilities
- FastAPI backend with SQLite persistence and SQLAlchemy models
- Dataset-aware ingestion pipeline for JSON, PDF, DOCX, XLSX, PPTX, HTML, and PNG sources
- Provenance tracking, alias handling, conflict management, and evidence-backed answers
- React + TypeScript + Vite frontend dashboard for querying the knowledge base
- Evaluation harness against the provided question set

## Running locally

1. Install Python dependencies:
   python -m pip install -r requirements.txt
2. Start the API:
   python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
   Or, from the `backend` directory:
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
3. Start the frontend:
   cd frontend && npm install && npm run dev -- --host 0.0.0.0 --port 5173

The project expects the source dataset under `./aegis-dataset` and the PDF question list at `./evaluation-questions.pdf`.

For a deployment platform that provides a `PORT` environment variable, use this start command:
`python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`

The backend uses package-relative imports and resolves the dataset and default SQLite database from the project root, so either local command works regardless of the current directory.

## Evidence model
The system preserves source provenance and distinguishes between verified facts, conflicting facts, version-scoped facts, inferred relationships, and information that could not be determined from the available evidence.

## Important note
The supplied dataset deliberately includes both authoritative manuals and low-trust/legacy records. The system does not automatically prefer newer files without checking revision metadata, and it documents uncertainty where the source set does not provide sufficient evidence.
