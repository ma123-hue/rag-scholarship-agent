from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.api.router import api_router
from app.core.config import ROOT_DIR, get_settings
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.user import User
from app.services.agent_runtime import get_agent_runtime
from app import models  # noqa: F401


settings = get_settings()


def run_startup_migrations() -> None:
    if not settings.resolved_database_url.startswith("sqlite"):
        return

    db_path = settings.resolved_database_url.removeprefix("sqlite:///")
    if not Path(db_path).exists():
        return

    with engine.begin() as conn:
        user_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()}
        if "is_admin" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"))


def init_db() -> None:
    run_startup_migrations()
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    target_tables = [table for table in Base.metadata.sorted_tables if table.name not in existing_tables]
    if target_tables:
        Base.metadata.create_all(bind=engine, tables=target_tables)

    with SessionLocal() as session:
        admin_exists = session.query(User).filter(User.username == settings.admin_username).first()
        if not admin_exists:
            session.add(
                User(
                    username=settings.admin_username,
                    password_hash=get_password_hash(settings.admin_password),
                    is_admin=True,
                )
            )
            session.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    try:
        yield
    finally:
        await get_agent_runtime().close()

app = FastAPI(
    title="Scholarship Application Agent",
    description="基于 RAG、DeepAgent 与 MCP 的高校奖助学金申请评估智能体系统",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
def healthcheck() -> dict:
    api_configured = bool(settings.llm_api_key and settings.llm_api_key != "sk-your-api-key")
    return {
        "status": "ok",
        "model_api_configured": api_configured,
        "chat_model": settings.llm_chat_model,
        "embedding_model": settings.embedding_model,
    }


# 在线 Demo 的单容器镜像会把 Vue 构建产物放在 frontend/dist。
# API 路由先注册，再由该兜底路由支持 Vue Router 的 history 模式。
frontend_dist = ROOT_DIR / "frontend" / "dist"
if frontend_dist.is_dir():
    assets_dir = frontend_dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        requested_file = (frontend_dist / full_path).resolve()
        if (
            full_path
            and requested_file.is_relative_to(frontend_dist.resolve())
            and requested_file.is_file()
        ):
            return FileResponse(requested_file)
        return FileResponse(frontend_dist / "index.html")
