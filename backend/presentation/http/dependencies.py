from __future__ import annotations

from backend.application.commands.meeting_import import SubmitMeetingImportCommand
from backend.application.use_cases.extract_meeting import ExtractMeetingUseCase
from backend.domain.ports import MeetingImportQueuePort
from backend.infrastructure.persistence.sqlite import SqliteMeetingsRepository
from backend.infrastructure.storage.blob import BlobStorageService
from backend.container import (
    get_blob_storage,
    get_extract_use_case,
    get_meeting_queue,
    get_meetings_repository,
)


def extraction_workflow() -> ExtractMeetingUseCase:
    return get_extract_use_case()


def data_repository() -> SqliteMeetingsRepository:
    return get_meetings_repository()


def blob_storage_service() -> BlobStorageService:
    storage = get_blob_storage()
    if storage is None:
        raise RuntimeError("Blob storage is not configured.")
    return storage


def meeting_queue() -> MeetingImportQueuePort:
    return get_meeting_queue()


def submit_import_command() -> SubmitMeetingImportCommand:
    return SubmitMeetingImportCommand(repository=get_meetings_repository(), queue=get_meeting_queue())
