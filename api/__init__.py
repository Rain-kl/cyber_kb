# api/__init__.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .kb_router import router as kb_router
from .memo_router import router as memo_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="KB Service API",
        description="API for monitoring and controlling the crawling service",
        version="1.0.0",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 允许所有源，生产环境中应该限制为特定域名
        allow_credentials=True,
        allow_methods=["*"],  # 允许所有HTTP方法
        allow_headers=["*"],  # 允许所有请求头
    )

    # Include the API router
    app.include_router(memo_router, prefix="/api/memory")
    app.include_router(kb_router, prefix="/api/kb")

    return app


app = create_app()
