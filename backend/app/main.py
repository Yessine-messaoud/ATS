import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.api.deps import get_llm
from app.config import get_settings
from app.db import new_session
from app.security.crypto import get_cipher
from app.security.logs import install_pii_filter
from app.services.tasks import Worker
from app.services.taxonomy import activate_stored_taxonomy

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    install_pii_filter()
    problems = settings.production_problems()
    if problems and settings.app_env == "production":
        raise RuntimeError("refusing to start in production: " + "; ".join(problems))
    for problem in problems:
        logging.getLogger("app").warning(problem)
    activate_stored_taxonomy()
    worker = Worker(new_session, get_llm, settings) if settings.ingestion_worker else None
    if worker:
        worker.start()
    yield
    if worker:
        worker.stop()


app = FastAPI(title=settings.app_name, version="0.1.0", debug=settings.debug, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(api_router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": f"{settings.app_name} is running"}


@app.get("/health")
def healthcheck() -> dict[str, object]:
    return {"status": "ok", "llm_provider": settings.llm_provider, "document_encryption": get_cipher().enabled}
