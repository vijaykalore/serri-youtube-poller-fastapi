import os
import asyncio
import pytest
import asyncio

from app.db import create_all_for_testing, drop_all_for_testing, Base

os.environ.setdefault("DISABLE_POLLER", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def setup_db_schema():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_all_for_testing(Base.metadata))
    yield
    loop.run_until_complete(drop_all_for_testing(Base.metadata))
