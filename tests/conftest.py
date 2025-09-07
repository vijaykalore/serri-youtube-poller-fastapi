import os
import asyncio
import pytest

os.environ.setdefault("DISABLE_POLLER", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
