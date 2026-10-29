"""HTTP routes, organised by domain."""

from fastapi import APIRouter

from . import candidates, jobs

router = APIRouter(prefix="/api")
router.include_router(candidates.router)
router.include_router(jobs.router)
