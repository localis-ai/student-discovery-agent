from sqlalchemy.orm import Session

from app.models.version import Version
from app.modules.version.crud.version import (
    crud_create_version,
    crud_get_current_version,
    crud_get_version_by_version_string,
)
from app.modules.version.schemas.version import VersionCreate


class VersionService:
    """Service layer for version management"""

    @staticmethod
    def get_current_version(db: Session) -> Version:
        """Get current application version"""
        version = crud_get_current_version(db)
        if not version:
            # Should not happen in production, but handle gracefully
            raise ValueError("No current version found in system")
        return version

    @staticmethod
    def create_new_version(db: Session, version_data: VersionCreate) -> Version:
        """
        Create and register new version

        Raises:
        - ValueError: If version already exists
        """
        # Check version doesn't already exist
        existing = crud_get_version_by_version_string(db, version_data.version)
        if existing:
            raise ValueError(f"Version {version_data.version} already exists")

        # Create version with automatic status management
        new_version = crud_create_version(
            db,
            version=version_data.version,
            description=version_data.description,
        )
        return new_version
