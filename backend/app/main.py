"""FastAPI application. Routers are added checkpoint by checkpoint."""
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from . import db
from .api import demo, documents, evidence, investigations, questions
from .config import settings
from .logging_utils import log_stage


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    log_stage("startup", llm_mode=settings.llm_mode, model=settings.openrouter_model, data_dir=settings.data_dir)
    yield


app = FastAPI(title="Document Investigator", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.monotonic()
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        log_stage(
            "http",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ms=int((time.monotonic() - started) * 1000),
        )
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    """Errors use the LLD shape: {"error": {"code", "message"}}."""
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


app.include_router(demo.router, prefix="/api")
app.include_router(investigations.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(questions.router, prefix="/api")
app.include_router(evidence.router, prefix="/api")
