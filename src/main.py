import logging
import time
from datetime import datetime

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from brotli_asgi import BrotliMiddleware
from api_analytics.fastapi import Analytics

from .config import config
from .auth import auth_router
from .journal import journal_router
from .github import github_router


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Validate configuration on startup
try:
    config.validate()
except ValueError as e:
    logger.error(f"Configuration error: {e}")
    raise

app = FastAPI(
    title="Hledger Server API",
    description="API for the Hledger mobile application",
    version="0.1.0",
    root_path=""
)

app.add_middleware(Analytics, api_key="bec0df76-4ce1-4c42-ba6c-02d0d27c53d3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compress responses
app.add_middleware(BrotliMiddleware, minimum_size=10_000)

# @app.middleware("http")
# async def add_proxy_headers(request: Request, call_next):
#     # Trust Cloudflare proxy headers
#     if "x-forwarded-proto" in request.headers:
#         request.scope["scheme"] = request.headers["x-forwarded-proto"]
#     if "x-forwarded-host" in request.headers:
#         request.scope["server"] = (request.headers["x-forwarded-host"], None)
#     response = await call_next(request)
#     return response

@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = id(request)

    start_time = time.time()
    start_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(
        f"Request {request_id}: {request.method} {request.url.path} - "
        f"Body: {await request.body()}"
    )

    response = await call_next(request)

    duration = time.time() - start_time
    logger.info(
        f"Request {request_id}: {request.method} {request.url.path} - "
        f"Start: {start_dt} - "
        f"Status: {response.status_code} - "
        f"Duration: {duration:.3f}s"
    )
    return response


# Global Exception Handlers for automatic error logging

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Log all HTTP exceptions automatically"""
    logger.error(
        f"HTTP Error | Method: {request.method} | Path: {request.url.path} | "
        f"Status: {exc.status_code} | Detail: {exc.detail}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Log all unexpected exceptions automaticall."""
    logger.error(
        f"Unexpected Error | Method: {request.method} | Path: {request.url.path} | "
        f"Error Type: {type(exc).__name__} | Message: {str(exc)}",
        exc_info=True
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


app.include_router(auth_router)
app.include_router(github_router)
app.include_router(journal_router)

@app.get("/")
async def root():
    return {
        "message": "Welcome to Hledger Mobile App API",
        "version": "0.1.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )
