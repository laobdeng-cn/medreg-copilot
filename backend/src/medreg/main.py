from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from medreg import __version__
from medreg.api.dependencies import close_knowledge_graph_driver
from medreg.api.router import api_router
from medreg.core.config import get_settings
from medreg.core.database import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await close_knowledge_graph_driver()
    await engine.dispose()

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=__version__,
    docs_url="/docs" if settings.app_env != "production" else None,
    lifespan=lifespan,
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.app_allowed_hosts,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": __version__,
        "docs": "/docs" if settings.app_env != "production" else "disabled",
    }
