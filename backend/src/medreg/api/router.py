from fastapi import APIRouter

from medreg.api.v1 import (
    agent,
    applications,
    documents,
    evaluation,
    health,
    knowledge_graph,
    regulations,
    retrieval,
    security,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(applications.router)
api_router.include_router(regulations.router)
api_router.include_router(knowledge_graph.router)
api_router.include_router(documents.router)
api_router.include_router(retrieval.router)
api_router.include_router(agent.router)
api_router.include_router(evaluation.router)
api_router.include_router(security.router)
