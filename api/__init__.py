# api/__init__.py

from fastapi import FastAPI
from .memo_router import router as memo_router
from .kb_router import router as kb_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="KB Service API",
        description="API for monitoring and controlling the crawling service",
        version="1.0.0",
    )

    # Include the API router
    app.include_router(memo_router, prefix="/api/memory")
    app.include_router(kb_router, prefix="/api/kb")

    return app


app = create_app()
