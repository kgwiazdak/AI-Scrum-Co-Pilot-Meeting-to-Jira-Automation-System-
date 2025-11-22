#!/bin/sh
set -e

# Sync intro voice samples from Azure Blob Storage
echo "Syncing intro voice samples..."
python -m backend.scripts.sync_voices

# Execute the main command
exec "$@"
