"""
NEUROGUT -- File Storage Service
==================================
Abstracted storage layer. Currently saves to local filesystem.
Swap to S3/MinIO by replacing save() and get_url() methods.
"""

import os
from pathlib import Path


class StorageService:
    """Local file storage for PDF reports."""

    def __init__(self, base_dir: str | Path | None = None):
        if base_dir is None:
            base_dir = Path(__file__).resolve().parents[1] / "reports"
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, file_key: str, data: bytes) -> str:
        """Save file and return local path."""
        file_path = self.base_dir / file_key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(data)
        return str(file_path)

    def get_path(self, file_key: str) -> str:
        """Get the full local path for a file key."""
        return str(self.base_dir / file_key)

    def exists(self, file_key: str) -> bool:
        return (self.base_dir / file_key).exists()

    def delete(self, file_key: str) -> bool:
        path = self.base_dir / file_key
        if path.exists():
            path.unlink()
            return True
        return False


# Module-level singleton
storage_service = StorageService()
