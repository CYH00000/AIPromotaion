# -*- coding: utf-8 -*-
# Derived from MediaCrawler (https://github.com/NanmiCoder/MediaCrawler).
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1; see LICENSE.

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.db_config import postgres_db_config


DATABASE_URL = URL.create(
    "postgresql+asyncpg",
    username=postgres_db_config["user"],
    password=postgres_db_config["password"],
    host=postgres_db_config["host"],
    port=int(postgres_db_config["port"]),
    database=postgres_db_config["db_name"],
)
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def collector_session() -> AsyncIterator[AsyncSession]:
    """Yield a transaction-bound session for collector-owned tables."""
    async with session_factory() as session:
        async with session.begin():
            yield session


def _upgrade_collector_schema() -> None:
    from alembic import command
    from alembic.config import Config

    project_root = Path(__file__).resolve().parents[1]
    command.upgrade(Config(str(project_root / "alembic.ini")), "head")


async def apply_collector_migrations() -> None:
    """Apply versioned application migrations without changing upstream metadata."""
    import asyncio

    await asyncio.to_thread(_upgrade_collector_schema)


async def close_collector_database() -> None:
    """Release database connections during application shutdown."""
    await engine.dispose()
