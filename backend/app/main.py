"""FastAPI 应用工厂。

干净环境即可启动：默认 offline provider、SQLite、无任何外部依赖。
所有 /api 业务路由都需要 X-Device-ID 头（伪匿名设备标识，无账户体系）。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import Settings
from .llm.base import LLMProvider
from .llm.factory import build_provider
from .logging_setup import configure_logging
from .prompt_service import PromptService
from .safety.guard import SafetyGuard
from .services.crisis_resources import CrisisResourceService

logger = logging.getLogger("mindpulse.app")


@dataclass
class AppContext:
    settings: Settings
    sessionmaker: sessionmaker
    provider: LLMProvider
    guard: SafetyGuard
    prompts: PromptService
    crisis: CrisisResourceService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings)

    engine_kwargs: dict = {}
    if settings.database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(settings.database_url, **engine_kwargs)

    from .models.db import Base

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    ctx = AppContext(
        settings=settings,
        sessionmaker=SessionLocal,
        provider=build_provider(settings),
        guard=SafetyGuard(),
        prompts=PromptService(),  # prompts 目录固定在 monorepo 根，无配置项
        crisis=CrisisResourceService(),
    )

    app = FastAPI(
        title="MindPulse API",
        version="0.1.0",
        description="情绪支持应用后端。不是医疗产品，不提供医学诊断或紧急服务。",
    )
    app.state.ctx = ctx

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", "X-Device-ID"],
    )

    # ---------- 访问日志：只有 method/path/status/耗时，无 body/query ----------
    @app.middleware("http")
    async def access_log(request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info("http %s %s -> %s %.0fms", request.method, request.url.path, response.status_code, duration_ms)
        return response

    # ---------- 公开路由 ----------
    from .api.routes_chat import router as chat_router
    from .api.routes_mood import router as mood_router
    from .api.routes_health import router as health_router
    from .api.routes_privacy import router as privacy_router
    from .api.routes_crisis import router as crisis_router

    app.include_router(chat_router, prefix="/api")
    app.include_router(mood_router, prefix="/api")
    app.include_router(health_router, prefix="/api")
    app.include_router(privacy_router, prefix="/api")
    app.include_router(crisis_router, prefix="/api")

    @app.get("/health", tags=["meta"])
    def liveness() -> dict:
        return {"status": "ok", "app": "mindpulse", "version": "0.1.0"}

    @app.get("/", tags=["meta"])
    def root() -> dict:
        return {
            "app": "MindPulse API",
            "notice": "MindPulse 提供情绪支持，不提供医学诊断或紧急服务",
            "docs": "/docs",
        }

    return app


# 供 `uvicorn app.main:app` 直接使用；配置全部来自环境变量，
# 默认 offline provider + SQLite，干净环境即可启动。
app = create_app()
