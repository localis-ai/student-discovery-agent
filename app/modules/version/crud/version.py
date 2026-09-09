from typing import Optional

from sqlalchemy.orm import Session

from app.models.version import Version


def crud_get_current_version(db: Session) -> Optional[Version]:
    """Get the current/active version"""
    return db.query(Version).filter(Version.is_current == True).first()


def crud_get_version_by_version_string(db: Session, version: str) -> Optional[Version]:
    """Get version by version string (e.g., '1.0.0')"""
    return db.query(Version).filter(Version.version == version).first()


def crud_create_version(
    db: Session,
    version: str,
    description: Optional[str] = None,
) -> Version:
    """
    Create new version and auto-manage status:
    1. Mark previous current as deprecated
    2. Create new version as current
    """
    # Find and mark previous current version as deprecated
    previous_current = db.query(Version).filter(Version.is_current == True).first()
    if previous_current:
        previous_current.is_deprecated = True
        previous_current.is_current = False
        db.add(previous_current)

    # Create new current version
    new_version = Version(
        version=version,
        description=description,
        is_current=True,
        is_deprecated=False,
    )
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    return new_version
