import httpx
from fastapi import APIRouter, HTTPException
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from medreg.api.dependencies import (
    DatabaseSession,
    KnowledgeGraphRepositoryDependency,
    ObjectStorageDependency,
)
from medreg.core.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "medreg-api",
        "milestone": "M5",
        "storage": "postgresql+minio+redis+qdrant+neo4j",
    }


@router.get("/ready")
async def readiness(
    session: DatabaseSession,
    storage: ObjectStorageDependency,
    graph: KnowledgeGraphRepositoryDependency,
) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc
    try:
        await storage.ready()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Object storage is unavailable") from exc
    redis = Redis.from_url(get_settings().redis_url)
    try:
        await redis.ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Task broker is unavailable") from exc
    finally:
        await redis.aclose()
    try:
        api_key = get_settings().qdrant_api_key_value
        headers = {"api-key": api_key} if api_key else None
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(
                f"{get_settings().qdrant_url}/healthz",
                headers=headers,
            )
            response.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Vector store is unavailable") from exc
    try:
        await graph.ready()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Knowledge graph is unavailable") from exc
    return {
        "status": "ready",
        "database": "postgresql",
        "objects": "minio",
        "tasks": "redis",
        "vectors": "qdrant",
        "graph": "neo4j",
    }
