from __future__ import annotations

import pytest

from backend.application.use_cases.extract_meeting import ExtractMeetingUseCase
from backend.schemas import ExtractionResult, IssueType, Task


class DummyUploadFile:
    def __init__(self, content: bytes, *, filename: str, content_type: str | None = None) -> None:
        self._content = content
        self.filename = filename
        self.content_type = content_type

    async def read(self) -> bytes:
        return self._content


class DummyExtractor:
    def __init__(self, result: ExtractionResult) -> None:
        self._result = result
        self.transcript = None

    def extract(self, transcript: str) -> ExtractionResult:
        self.transcript = transcript
        return self._result


class DummyRepository:
    def __init__(self) -> None:
        self.captured: dict[str, str | None] | None = None

    def store_meeting_and_result(
        self,
        filename: str,
        transcript: str,
        result_model: ExtractionResult,
        *,
        meeting_id: str | None = None,
        title: str | None = None,
        started_at: str | None = None,
    ) -> tuple[str, str]:
        self.captured = {
            "filename": filename,
            "title": title,
            "started_at": started_at,
            "transcript": transcript,
            "meeting_id": meeting_id,
            "tasks": len(result_model.tasks),
        }
        return meeting_id or "meeting-id", "run-id"

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_extract_meeting_use_case_persists_custom_metadata(anyio_backend):
    result = ExtractionResult(
        tasks=[
            Task(
                summary="Follow up",
                description="Discuss blockers",
                issue_type=IssueType.TASK,
            )
        ]
    )
    extractor = DummyExtractor(result)
    repo = DummyRepository()
    workflow = ExtractMeetingUseCase(
        blob_storage=None,
        transcription=None,
        extractor=extractor,
        meetings_repo=repo,
        telemetry=None,
    )

    upload = DummyUploadFile(b"Meeting transcript line", filename="notes.txt", content_type="text/plain")
    await workflow(upload, title="Sprint Planning", started_at="2024-10-01T12:00:00Z")

    assert repo.captured is not None
    assert repo.captured["title"] == "Sprint Planning"
    assert repo.captured["started_at"] == "2024-10-01T12:00:00Z"
    assert repo.captured["filename"] == "notes.txt"
