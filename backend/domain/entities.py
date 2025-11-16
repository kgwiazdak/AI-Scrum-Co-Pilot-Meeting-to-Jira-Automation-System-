from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MeetingImportJob:
    meeting_id: str
    title: str
    started_at: str
    blob_url: str
    original_filename: str | None = None
