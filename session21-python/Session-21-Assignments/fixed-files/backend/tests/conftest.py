import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app


@pytest.fixture()
def client():
    # Fresh schema per test so tests never depend on each other or on a real Postgres.
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:
        yield c
