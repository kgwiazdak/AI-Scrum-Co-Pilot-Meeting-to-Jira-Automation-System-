from __future__ import annotations

from functools import lru_cache

from backend.application.use_cases.extract_meeting import ExtractMeetingUseCase
from backend.infrastructure.jira import JiraClient
from backend.infrastructure.llm.task_extractor import LLMExtractor
from backend.infrastructure.persistence.sqlite import SqliteMeetingsRepository
from backend.infrastructure.queue.background import BackgroundMeetingImportQueue
from backend.infrastructure.storage.blob import BlobStorageService
from backend.infrastructure.telemetry.mlflow_adapter import MLflowTelemetryAdapter
from backend.infrastructure.transcription.azure_conversation import (
    AzureConversationTranscriber,
    SUPPORTED_AUDIO_EXTENSIONS,
)
from backend.settings import get_settings


@lru_cache(maxsize=1)
def get_blob_storage() -> BlobStorageService | None:
    cfg = get_settings().blob_storage
    if not cfg.container_name or not cfg.connection_string:
        return None
    return BlobStorageService(
        container_name=cfg.container_name,
        connection_string=cfg.connection_string,
    )


@lru_cache(maxsize=1)
def get_transcriber() -> AzureConversationTranscriber | None:
    cfg = get_settings().azure_speech
    if not cfg.key or not cfg.region:
        return None
    return AzureConversationTranscriber(
        key=cfg.key,
        region=cfg.region,
        language=cfg.language,
        sample_rate=cfg.sample_rate,
    )


@lru_cache(maxsize=1)
def get_meetings_repository() -> SqliteMeetingsRepository:
    cfg = get_settings().database
    return SqliteMeetingsRepository(cfg.url)


@lru_cache(maxsize=1)
def get_telemetry() -> MLflowTelemetryAdapter:
    return MLflowTelemetryAdapter()


@lru_cache(maxsize=1)
def get_extractor() -> LLMExtractor:
    return LLMExtractor()


@lru_cache(maxsize=1)
def get_extract_use_case() -> ExtractMeetingUseCase:
    blob = get_blob_storage()
    transcription = get_transcriber()
    repo = get_meetings_repository()
    telemetry = get_telemetry()
    extractor = get_extractor()
    return ExtractMeetingUseCase(
        blob_storage=blob,
        transcription=transcription,
        extractor=extractor,
        meetings_repo=repo,
        telemetry=telemetry,
        audio_extensions=SUPPORTED_AUDIO_EXTENSIONS,
    )


@lru_cache(maxsize=1)
def get_meeting_queue() -> BackgroundMeetingImportQueue:
    use_case = get_extract_use_case()
    return BackgroundMeetingImportQueue(use_case.process_job)


@lru_cache(maxsize=1)
def get_jira_client() -> JiraClient | None:
    cfg = get_settings().jira
    if not cfg.base_url or not cfg.email or not cfg.api_token or not cfg.project_key:
        return None
    try:
        return JiraClient(
            base_url=cfg.base_url,
            email=cfg.email,
            api_token=cfg.api_token,
            project_key=cfg.project_key,
            story_points_field=cfg.story_points_field,
        )
    except ValueError:
        return None
