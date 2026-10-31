"""HTTP routes, organised by domain."""

from fastapi import APIRouter

from . import admin, agent, applications, audit, auth, candidates, jobs, matches, organization, portal, privacy

router = APIRouter(prefix="/api")
router.include_router(auth.router)
router.include_router(candidates.router)
router.include_router(jobs.router)
router.include_router(matches.router)
router.include_router(applications.router)
router.include_router(agent.router)
router.include_router(audit.router)
router.include_router(privacy.router)
router.include_router(organization.router)
router.include_router(admin.router)
router.include_router(portal.public)
router.include_router(portal.router)
