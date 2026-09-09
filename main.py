from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import StreamingResponse
from fastapi.routing import APIRoute
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.vault_loader import load_config
from app.db import get_db
from app.exception_handlers.error_middleware import ErrorStandardizationMiddleware
from app.exception_handlers.http_exception import custom_http_exception_handler, general_exception_handler
from app.modules import route
from app.modules.common.middleware import ResponseWrappingMiddleware, TimeoutMiddleware
from app.modules.common.utils.logging import FastAPILoggingMiddleware, logger, setup_logging
from app.modules.common.utils.request_tracking import RequestTrackingMiddleware

# from app.modules.common.utils.throttling import ThrottlingMiddleware

load_config()
setup_logging("DEBUG")


def custom_generate_unique_id(route: APIRoute) -> str:
    """
    Custom function to generate unique operation IDs for OpenAPI schema.
    This creates cleaner method names for generated client code.
    """
    if route.tags:
        return f"{route.tags[0]}_{route.name}"
    return route.name


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Hard-code valid OpenAPI version at the root
    openapi_schema["openapi"] = "3.0.3"

    # Khởi tạo components nếu chưa có để tránh lỗi KeyError
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}

    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png",
    }

    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    openapi_schema["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.db import init_database

    init_database()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    license_info={"name": "MIT"},
    redirect_slashes=False,
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)


# Add middleware to log all requests
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"→ {request.method} {request.url}")
    response = await call_next(request)
    status = response.status_code if hasattr(response, "status_code") else "streaming"
    media = getattr(response, "media_type", "unknown")
    logger.success(f"← {response.__class__.__name__}({status}, {media})")
    return response


app.openapi = custom_openapi

# Middleware order matters (added in reverse order - LIFO):
# 1. ErrorStandardizationMiddleware (outer) - catches unhandled exceptions
# 2. TimeoutMiddleware - handles timeout exceptions
# 3. RequestTrackingMiddleware - extracts/generates request_id and trace_id
# 4. CORSMiddleware - handles CORS
# 5. FastAPILoggingMiddleware - logs requests (inner)

# Add ErrorStandardizationMiddleware FIRST (runs last in chain, catches all exceptions)
app.add_middleware(ErrorStandardizationMiddleware)

# Add TimeoutMiddleware to handle timeout exceptions
app.add_middleware(TimeoutMiddleware)

# Add RequestTrackingMiddleware before other middleware to track request_id and trace_id
app.add_middleware(RequestTrackingMiddleware)

# Add ResponseWrappingMiddleware to automatically wrap all successful 2xx responses
app.add_middleware(ResponseWrappingMiddleware)

_cors_origins = [str(o).rstrip("/") for o in settings.BACKEND_CORS_ORIGINS] if getattr(settings, "BACKEND_CORS_ORIGINS", None) else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)
app.add_middleware(FastAPILoggingMiddleware)
# Add throttling middleware for rate limiting
# app.add_middleware(ThrottlingMiddleware)

# Register exception handlers for standardized error responses
app.add_exception_handler(HTTPException, custom_http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

app.include_router(route)


@app.get("/health")
def health(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Comprehensive health check endpoint that tests all services
    """
    health_data = {
        "timestamp": "2025-09-10T12:00:00Z",
        "status": "healthy",
        "services": {},
    }

    # Test database connection
    try:
        db.query(text("SELECT 1"))
        db.commit()
        health_data["services"]["database"] = {
            "status": "connected",
            "server": settings.POSTGRES_SERVER,
            "database": settings.POSTGRES_DB,
        }
    except Exception as e:
        health_data["services"]["database"] = {
            "status": "disconnected",
            "error": str(e),
        }
        health_data["status"] = "degraded"

    # Test Redis connection
    try:
        from app.modules.common.utils.redis import get_redis_client

        redis_client = get_redis_client()
        redis_client.ping()
        redis_info = redis_client.info()
        health_data["services"]["redis"] = {
            "status": "connected",
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "db": settings.REDIS_DB,
            "version": redis_info.get("redis_version", "unknown"),
        }
    except Exception as e:
        health_data["services"]["redis"] = {"status": "disconnected", "error": str(e)}
        health_data["status"] = "degraded"

    # Test Neo4j connection
    try:
        from app.modules.common.utils.neo4j_client import neo4j_health_check

        if neo4j_health_check():
            health_data["services"]["neo4j"] = {
                "status": "connected",
                "uri": settings.NEO4J_URI,
            }
        else:
            health_data["services"]["neo4j"] = {"status": "disconnected"}
            health_data["status"] = "degraded"
    except Exception as e:
        health_data["services"]["neo4j"] = {"status": "error", "error": str(e)}
        health_data["status"] = "degraded"

    # Test MinIO connection
    try:
        from app.modules.common.utils.minio import health_check as minio_health_check

        minio_healthy = minio_health_check()
        if minio_healthy:
            health_data["services"]["minio"] = {
                "status": "connected",
                "endpoint": settings.MINIO_ENDPOINT,
                "bucket": settings.MINIO_BUCKET_NAME,
                "public_bucket": settings.MINIO_PUBLIC_BUCKET_NAME,
                "secure": settings.MINIO_SECURE,
            }
        else:
            health_data["services"]["minio"] = {"status": "disconnected"}
            health_data["status"] = "degraded"
    except Exception as e:
        health_data["services"]["minio"] = {"status": "error", "error": str(e)}
        health_data["status"] = "degraded"

    # Raise error if any critical service is down
    critical_services = ["database", "redis"]
    for service in critical_services:
        if health_data["services"].get(service, {}).get("status") != "connected":
            raise HTTPException(status_code=503, detail=health_data)

    return health_data


@app.get("/health/database")
def health_database(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Database health check endpoint
    """
    try:
        # Test database connection with a simple query
        db.query(text("SELECT 1"))
        db.commit()

        # Get database info
        result = db.execute(text("SELECT version() as version, current_database() as database, current_user as user"))
        row = result.fetchone()
        version = row[0] if row else "Unknown"
        database = row[1] if row else "Unknown"
        user = row[2] if row else "Unknown"

        return {
            "status": "connected",
            "database": database,
            "user": user,
            "version": version,
            "server": settings.POSTGRES_SERVER,
            "port": settings.POSTGRES_PORT,
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "disconnected",
                "error": str(e),
                "database": settings.POSTGRES_DB,
                "server": settings.POSTGRES_SERVER,
            },
        )


@app.get("/health/redis")
def health_redis() -> Dict[str, Any]:
    """
    Redis health check endpoint
    """
    try:
        from app.modules.common.utils.redis import get_redis_client

        redis_client = get_redis_client()

        # Test connection
        redis_client.ping()

        # Get Redis info
        info = redis_client.info()
        memory_info = redis_client.info("memory")

        return {
            "status": "connected",
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "db": settings.REDIS_DB,
            "version": info.get("redis_version", "unknown"),
            "uptime_seconds": info.get("uptime_in_seconds", 0),
            "connected_clients": info.get("connected_clients", 0),
            "memory_used": memory_info.get("used_memory_human", "unknown"),
            "memory_peak": memory_info.get("used_memory_peak_human", "unknown"),
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "disconnected",
                "error": str(e),
                "host": settings.REDIS_HOST,
                "port": settings.REDIS_PORT,
            },
        )


@app.get("/health/minio")
def health_minio() -> Dict[str, Any]:
    """
    MinIO health check endpoint
    """
    try:
        from app.modules.common.utils.minio import get_minio_client

        # Test connection by listing buckets
        minio_client = get_minio_client()
        try:
            buckets = minio_client.list_buckets()
            bucket_names = [bucket.name for bucket in buckets]

            # Check if our buckets exist
            main_bucket_exists = settings.MINIO_BUCKET_NAME in bucket_names
            public_bucket_exists = settings.MINIO_PUBLIC_BUCKET_NAME in bucket_names

            return {
                "status": "connected",
                "endpoint": settings.MINIO_ENDPOINT,
                "secure": settings.MINIO_SECURE,
                "main_bucket": {
                    "name": settings.MINIO_BUCKET_NAME,
                    "exists": main_bucket_exists,
                },
                "public_bucket": {
                    "name": settings.MINIO_PUBLIC_BUCKET_NAME,
                    "exists": public_bucket_exists,
                },
                "total_buckets": len(bucket_names),
                "bucket_names": bucket_names[:10],  # Limit to first 10 for brevity
            }
        except Exception as bucket_error:
            return {
                "status": "connected",
                "endpoint": settings.MINIO_ENDPOINT,
                "secure": settings.MINIO_SECURE,
                "bucket_check_error": str(bucket_error),
            }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "disconnected",
                "error": str(e),
                "endpoint": settings.MINIO_ENDPOINT,
                "secure": settings.MINIO_SECURE,
            },
        )


@app.get("/health/services")
def health_services(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Quick overview of all services status
    """
    services_status = {}

    # Database
    try:
        db.query(text("SELECT 1"))
        services_status["database"] = "✅ connected"
    except Exception:
        services_status["database"] = "❌ disconnected"

    # Redis
    try:
        from app.modules.common.utils.redis import get_redis_client

        get_redis_client().ping()
        services_status["redis"] = "✅ connected"
    except Exception:
        services_status["redis"] = "❌ disconnected"

    # MinIO
    try:
        from app.modules.common.utils.minio import get_minio_client

        client = get_minio_client()
        client.list_buckets()  # thử kết nối
        services_status["minio"] = "✅ connected"
    except Exception as e:
        services_status["minio"] = f"❌ disconnected ({e})"

    return {
        "timestamp": "2025-09-10T12:00:00Z",
        "services": services_status,
        "overall_status": "healthy" if all("✅" in status for status in services_status.values()) else "degraded",
    }


@app.get("/download")
def download_file(object_name: str):
    from app.modules.common.utils.minio import download_file_from_minio

    filename_only = object_name.split("/")[-1]
    bucket_name = object_name.split("/")[0]

    file_bytes = download_file_from_minio(bucket_name, filename_only)
    if not file_bytes:
        raise HTTPException(status_code=404, detail="File not found")

    return StreamingResponse(iter([file_bytes]), media_type="application/octet-stream", headers={"Content-Disposition": f"attachment; filename={filename_only}"})


@app.get("/")
def read_root() -> Dict[str, Any]:
    return {
        "name": settings.PROJECT_NAME,
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
