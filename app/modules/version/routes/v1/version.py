from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.constants.messages import MessageConstants
from app.db import get_db
from app.modules.common.schemas.common import ApiResponse
from app.modules.common.utils.logging import logger
from app.modules.version.schemas.version import (
    VersionApiResponse,
    VersionCreate,
    VersionResponse,
)
from app.modules.version.services.version import VersionService

router = APIRouter(tags=["Version"], prefix="/versions")


# ===== GET ENDPOINT: Current Version (PUBLIC - NO AUTH) =====
@router.get("", response_model=VersionApiResponse, status_code=status.HTTP_200_OK)
def get_current_version(
    db: Session = Depends(get_db),
):
    """
    Get current application version

    Returns:
    - Current/active version with metadata
    - Only ONE version marked as current
    - No authentication required
    """
    try:
        logger.debug("Fetching current application version")
        version = VersionService.get_current_version(db)
        response_data = VersionResponse.model_validate(version)

        logger.info(f"Current version returned: {version.version}")
        return ApiResponse(
            success=True,
            message=MessageConstants.VERSION_RETRIEVED_SUCCESS,
            data=response_data,
        )
    except ValueError as e:
        logger.error(f"Version not found: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No current version found",
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching version: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===== POST ENDPOINT: Create New Version (PUBLIC - NO AUTH) =====
@router.post("", response_model=VersionApiResponse, status_code=status.HTTP_201_CREATED)
def create_version(
    version_data: VersionCreate,
    db: Session = Depends(get_db),
):
    """
    Create and register new application version

    Behavior:
    - Validates semantic version format (x.x.x)
    - Auto-marks previous version as deprecated
    - New version becomes current
    - No authentication required

    Returns:
    - Created version with is_current=True
    """
    try:
        logger.debug(f"Creating new version: {version_data.version}")

        # Create version (service handles auto-status management)
        new_version = VersionService.create_new_version(db, version_data)
        response_data = VersionResponse.model_validate(new_version)

        logger.info(f"Version created successfully: {new_version.version}")
        return ApiResponse(
            success=True,
            message=MessageConstants.VERSION_CREATED_SUCCESS,
            data=response_data,
        )
    except ValueError as e:
        logger.warning(f"Validation error creating version: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error creating version: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
