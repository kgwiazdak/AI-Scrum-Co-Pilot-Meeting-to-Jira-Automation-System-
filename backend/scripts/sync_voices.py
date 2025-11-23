"""Sync intro voice samples from Azure Blob Storage at startup."""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_WORKERS = os.getenv("AZURE_STORAGE_CONTAINER_WORKERS")
INTRO_AUDIO_DIR = os.getenv("INTRO_AUDIO_DIR", "data/voices")


def sync_voices() -> None:
    """Download intro_*.mp3 files from Azure Blob Storage.

    Skips gracefully if Azure credentials are not configured.
    Only downloads files that don't already exist locally.
    """
    if not AZURE_STORAGE_CONNECTION_STRING or not AZURE_STORAGE_CONTAINER_WORKERS:
        logger.info("Voice sync skipped: Azure Storage not configured")
        return

    target_dir = Path(INTRO_AUDIO_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        from azure.storage.blob import BlobServiceClient

        blob_service = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        container_client = blob_service.get_container_client(AZURE_STORAGE_CONTAINER_WORKERS)

        for blob in container_client.list_blobs():
            if blob.name.startswith("intro_") and blob.name.endswith(".mp3"):
                local_path = target_dir / blob.name
                if local_path.exists():
                    logger.debug("Skipping existing file: %s", blob.name)
                    continue

                logger.info("Downloading: %s", blob.name)
                blob_client = container_client.get_blob_client(blob.name)
                data = blob_client.download_blob().readall()
                local_path.write_bytes(data)

        logger.info("Voice sync complete")

    except Exception as e:
        logger.warning("Failed to connect to Azure Storage: %s", e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync_voices()
