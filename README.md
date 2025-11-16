# Sprint Planning Copilot

AI assistant that turns raw meeting recordings into Jira-ready backlog items. The system ingests files uploaded through the web UI, stores the originals in Azure Blob Storage, processes them asynchronously with FastAPI workers, persists the structured tasks in SQLite, logs the whole run to MLflow, and finally lets reviewers approve tasks into Jira with a single click.

```
Browser ──upload──▶ Azure Blob
            │
            ▼
        FastAPI API ──queue job──▶ Async worker
            │                        │
            │                        ├─▶ Azure Speech / LLM extraction
            │                        └─▶ SQLite + MLflow logging
            │
            └──REST──▶ React/Vite UI (meetings + review)
```

## Highlights

- **Event-driven ingestion** – uploads go straight to blob storage, the API only stores a stub and enqueues background work.
- **Automatic transcription & extraction** – Azure Conversation transcription plus an LLM prompt convert meetings into normalized tasks.
- **Live status dashboards** – meetings view auto-refreshes while jobs are queued/processing; the Review & Approve tab polls drafts every 5 s.
- **One-click Jira pushes** – approving tasks creates properly formatted Jira issues (labels are sanitized automatically) and records the issue key/URL.
- **Telemetry by default** – every import logs transcripts, prompts, metrics, and artifacts to MLflow for auditing.

## Repository Tour

| Path | Description |
| --- | --- |
| `backend/presentation/http/ui_router.py` | FastAPI router exposing uploads, meetings, tasks, review actions, and Jira pushes. |
| `backend/application/...` | Commands/use-cases/services that orchestrate meeting imports and Jira pushes. |
| `backend/infrastructure/...` | SQLite repository, blob storage adapter, queue, telemetry, Azure Speech, LLM, and Jira client. |
| `frontend/src/app` & `frontend/src/features` | React/Vite UI (meetings table, meeting detail tasks, review queue). |
| `frontend/src/api` | Axios + React Query hooks (auto polling, optimistic updates, Jira mutations). |
| `backend/tests` | Pytest coverage for ingestion, MLflow telemetry, and Jira push logic. |

## Requirements

- Python 3.11+
- Poetry 2.x
- Node.js 18+
- FFmpeg (for audio transcription)
- Azure Blob Storage account (SAS uploads)
- Azure Speech + OpenAI (or set `MOCK_LLM=1` for deterministic dev)
- Jira Cloud project & API token
- Optional: Docker + Docker Compose for the all-in-one stack

## Configuration

Create `.env` (backend) and `.env.development` (frontend). Key variables:

| Purpose | Variables |
| --- | --- |
| Azure Blob uploads | `AZURE_STORAGE_CONNECTION_STRING`, `AZURE_STORAGE_CONTAINER_NAME`, `AZURE_STORAGE_CONTAINER_WORKERS` (intro voices) |
| Azure Speech | `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `AZURE_SPEECH_LANGUAGE`, `TRANSCRIBER_SAMPLE_RATE` |
| LLM extraction | `LLM_PROVIDER`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`, `OPENAI_MODEL`, `LLM_TEMPERATURE`, `MOCK_LLM=1` (local stub) |
| Database | `DB_URL` (defaults to `sqlite:///./app.db`) |
| Jira push | `JIRA_BASE_URL` (e.g. `https://importantwork.atlassian.net`), `JIRA_PROJECT_KEY` (e.g. `SCRUM`), `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_STORY_POINTS_FIELD` (custom field id, optional) |
| Telemetry | `MLFLOW_TRACKING_URI`, `MLFLOW_EXPERIMENT_NAME` |
| Frontend | `.env.development` → `VITE_API_URL=http://localhost:8000/api` |

CORS reminder: allow `http://localhost:4173` for `PUT,OPTIONS` in your Azure Blob container so browser uploads succeed.

## Development Setup

### Backend

```bash
poetry install --with dev
cp .env.sample .env  # then edit values described above
poetry run uvicorn backend.app:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.development.sample .env.development  # ensure VITE_API_URL is set
npm run dev
```

Navigate to `http://localhost:4173`. The UI talks to FastAPI via the configured API URL and polls for meetings/drafts automatically.

## Docker Compose

Run the full stack (API, MLflow, Nginx-served frontend):

```bash
docker compose up --build
```

Ports: API `8000`, MLflow `5000`, frontend `4173`. The frontend container proxies API calls to `/api`.

## Typical Workflow

1. **Generate SAS** – UI `POST /api/uploads/blob` returns `uploadUrl`, `blobUrl`, `meetingId`.
2. **Upload File** – browser `PUT` directly to Azure Blob Storage using the SAS URL.
3. **Import Meeting** – UI `POST /api/meetings/import` with metadata + `blobUrl`. API stores a `queued` stub and enqueues a worker job.
4. **Background processing** – worker downloads the blob, runs transcription + LLM extraction, persists transcript/tasks, and logs the run to MLflow. Meeting status transitions `queued → processing → completed/failed`.
5. **Review & approve** – reviewers use the Meetings detail page or the Review tab to edit drafts inline. Approving pushes to Jira and records `jiraIssueKey/url` on each task.

## Jira Integration Notes

- Approvals call `POST /api/tasks/bulk-approve` which in turn uses `PushTasksToJiraService`.
- Labels are automatically sanitized (lowercase, spaces/invalid characters → `-`, empty labels dropped) to satisfy Jira’s restrictions.
- If Jira rejects a payload the API returns HTTP 502 with the Jira message so the UI can display the error.

## Telemetry & Storage

- SQLite lives at `app.db` by default; schema migrations are handled automatically at startup.
- MLflow artifacts land under `data/mlflow/artifacts/…`. Keep the MLflow service running (docker compose does this automatically) to inspect past runs.

## Testing

```bash
poetry run pytest backend/tests
```

This exercises ingestion orchestration, MLflow logging, Jira pushing, and the voice-profile flow. Add frontend/unit tests under `frontend/tests/` (Playwright smoke scaffold exists) before shipping major UI changes.

### Voice Samples & Diarization

- Store intro clips in the workers container (blobs like `intro_Adrian_Puchacki.mp3`). On startup the backend syncs missing files into `data/voices/` and creates/updates matching user records.
- During transcription, the Azure Conversation transcriber prepends these intros so diarized speakers can be matched to real names. Tasks from matched speakers arrive pre-assigned in the UI; unknown voices stay unassigned until you add a new intro sample.
- When a teammate joins, drop their intro clip in the workers container, restart the backend to sync, and confirm they show up under `/api/users`. As soon as their Jira account is known (either prefilled or auto-looked-up during approval), tasks will push into Jira under their name.

## Troubleshooting

- **Uploads fail from browser** – ensure Azure Storage CORS allows your frontend origin.
- **Duplicate column logs** – harmless; the SQLite auto-migration ensures Jira columns exist on startup.
- **Jira rejects approvals** – check the API response; usually caused by missing required fields or invalid custom field/label values.
- **Long-running jobs** – the review + meeting views poll; you can also tail the worker logs for detailed telemetry.

## Contributing

1. Create a feature branch.
2. Make sure `poetry run pytest` passes.
3. Keep frontend/backend types in sync (`backend/domain/status.py` ↔ `frontend/src/types/index.ts`).
4. Update this README if you add new configuration knobs or workflow steps.

Happy planning! 🎯
