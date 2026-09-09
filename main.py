from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, StreamingResponse
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


@app.get("/", response_class=HTMLResponse)
def read_root():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Vercel + FastAPI</title>
        <link rel="icon" type="image/x-icon" href="/favicon.ico">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
                background-color: #000000;
                color: #ffffff;
                line-height: 1.6;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
            }

            header {
                border-bottom: 1px solid #333333;
                padding: 0;
            }

            nav {
                max-width: 1200px;
                margin: 0 auto;
                display: flex;
                align-items: center;
                padding: 1rem 2rem;
                gap: 2rem;
            }

            .logo {
                font-size: 1.25rem;
                font-weight: 600;
                color: #ffffff;
                text-decoration: none;
            }

            .nav-links {
                display: flex;
                gap: 1.5rem;
                margin-left: auto;
            }

            .nav-links a {
                text-decoration: none;
                color: #888888;
                padding: 0.5rem 1rem;
                border-radius: 6px;
                transition: all 0.2s ease;
                font-size: 0.875rem;
                font-weight: 500;
            }

            .nav-links a:hover {
                color: #ffffff;
                background-color: #111111;
            }

            main {
                flex: 1;
                max-width: 1200px;
                margin: 0 auto;
                padding: 4rem 2rem;
                display: flex;
                flex-direction: column;
                align-items: center;
                text-align: center;
            }

            .hero {
                margin-bottom: 3rem;
            }

            .hero-code {
                margin-top: 2rem;
                width: 100%;
                max-width: 900px;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            }

            .hero-code pre {
                background-color: #0a0a0a;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 1.5rem;
                text-align: left;
                grid-column: 1 / -1;
            }

            h1 {
                font-size: 3rem;
                font-weight: 700;
                margin-bottom: 1rem;
                background: linear-gradient(to right, #ffffff, #888888);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }

            .subtitle {
                font-size: 1.25rem;
                color: #888888;
                margin-bottom: 2rem;
                max-width: 600px;
            }

            .cards {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 1.5rem;
                width: 100%;
                max-width: 900px;
            }

            .card {
                background-color: #111111;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 1.5rem;
                transition: all 0.2s ease;
                text-align: left;
            }

            .card:hover {
                border-color: #555555;
                transform: translateY(-2px);
            }

            .card h3 {
                font-size: 1.125rem;
                font-weight: 600;
                margin-bottom: 0.5rem;
                color: #ffffff;
            }

            .card p {
                color: #888888;
                font-size: 0.875rem;
                margin-bottom: 1rem;
            }

            .card a {
                display: inline-flex;
                align-items: center;
                color: #ffffff;
                text-decoration: none;
                font-size: 0.875rem;
                font-weight: 500;
                padding: 0.5rem 1rem;
                background-color: #222222;
                border-radius: 6px;
                border: 1px solid #333333;
                transition: all 0.2s ease;
            }

            .card a:hover {
                background-color: #333333;
                border-color: #555555;
            }

            .status-badge {
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
                background-color: #0070f3;
                color: #ffffff;
                padding: 0.25rem 0.75rem;
                border-radius: 20px;
                font-size: 0.75rem;
                font-weight: 500;
                margin-bottom: 2rem;
            }

            .status-dot {
                width: 6px;
                height: 6px;
                background-color: #00ff88;
                border-radius: 50%;
            }

            pre {
                background-color: #0a0a0a;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 1rem;
                overflow-x: auto;
                margin: 0;
            }

            code {
                font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
                font-size: 0.85rem;
                line-height: 1.5;
                color: #ffffff;
            }

            /* Syntax highlighting */
            .keyword {
                color: #ff79c6;
            }

            .string {
                color: #f1fa8c;
            }

            .function {
                color: #50fa7b;
            }

            .class {
                color: #8be9fd;
            }

            .module {
                color: #8be9fd;
            }

            .variable {
                color: #f8f8f2;
            }

            .decorator {
                color: #ffb86c;
            }

            @media (max-width: 768px) {
                nav {
                    padding: 1rem;
                    flex-direction: column;
                    gap: 1rem;
                }

                .nav-links {
                    margin-left: 0;
                }

                main {
                    padding: 2rem 1rem;
                }

                h1 {
                    font-size: 2rem;
                }

                .hero-code {
                    grid-template-columns: 1fr;
                }

                .cards {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        <header>
            <nav>
                <a href="/" class="logo">Vercel + FastAPI</a>
                <div class="nav-links">
                    <a href="/docs">API Docs</a>
                    <a href="/api/data">API</a>
                </div>
            </nav>
        </header>
        <main>
            <div class="hero">
                <h1>Vercel + FastAPI</h1>
                <div class="hero-code">
                    <pre><code><span class="keyword">from</span> <span class="module">fastapi</span> <span class="keyword">import</span> <span class="class">FastAPI</span>

<span class="variable">app</span> = <span class="class">FastAPI</span>()

<span class="decorator">@app.get</span>(<span class="string">"/"</span>)
<span class="keyword">def</span> <span class="function">read_root</span>():
    <span class="keyword">return</span> {<span class="string">"Python"</span>: <span class="string">"on Vercel"</span>}</code></pre>
                </div>
            </div>

            <div class="cards">
                <div class="card">
                    <h3>Interactive API Docs</h3>
                    <p>Explore this API's endpoints with the interactive Swagger UI. Test requests and view response schemas in real-time.</p>
                    <a href="/docs">Open Swagger UI →</a>
                </div>

                <div class="card">
                    <h3>Sample Data</h3>
                    <p>Access sample JSON data through our REST API. Perfect for testing and development purposes.</p>
                    <a href="/api/data">Get Data →</a>
                </div>

            </div>
        </main>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
