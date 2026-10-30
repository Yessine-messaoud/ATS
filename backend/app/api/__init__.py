"""HTTP routes, organised by domain."""

from fastapi import APIRouter

from . import agent, applications, candidates, jobs, matches

router = APIRouter(prefix="/api")
router.include_router(candidates.router)
router.include_router(jobs.router)
router.include_router(matches.router)
router.include_router(applications.router)
router.include_router(agent.router)
