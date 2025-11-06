# tests/test_users.py
import itertools
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool  # using this so the in-memory DB stays consistent


from app.main import app, get_db
from app.models import Base

TEST_DB_URL = "sqlite+pysqlite:///:memory:"

# Using an in-memory DB for testing (so it's fast + clean)
engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(bind=engine)

@pytest.fixture
def client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    # Create a TestClient for the app
    with TestClient(app) as c:
        yield c

# Helper to create users
_counter = itertools.count(1)
def _create_user(client, **overrides):
    n = next(_counter)
    payload = {
        "name": f"User{n}",
        "email": f"user{n}@atu.ie",
        "age": 25,
        "student_id": f"S{1000000 + n}",
    }
    payload.update(overrides)
    r = client.post("/api/users", json=payload)
    assert r.status_code == 201, f"Create failed: {r.status_code} {r.text}"
    return r.json()

# Test cases
def test_create_user(client):
    data = _create_user(client)
    assert "id" in data and isinstance(data["id"], int)
    assert data["email"].startswith("user")

# Test  for listing users
def test_list_users(client):
    _create_user(client, name="Ann", email="ann@atu.ie", student_id="S1111111")
    _create_user(client, name="Ben", email="ben@atu.ie", student_id="S2222222")
    r = client.get("/api/users")
    assert r.status_code == 200
    users = r.json()
    names = {u["name"] for u in users}
    assert {"Ann", "Ben"}.issubset(names)

# Test for getting a user by ID
def test_get_user(client):
    created = _create_user(client)
    uid = created["id"] # Get user ID
    r = client.get(f"/api/users/{uid}")
    assert r.status_code == 200
    assert r.json()["id"] == uid

# Test for conflict on duplicate email
def test_conflict_on_duplicate_email(client):
    _create_user(client, email="duplicate@atu.ie", student_id="S3333333")
    r = client.post(
        "/api/users",
        json={"name": "Kate", "email": "duplicate@atu.ie", "age": 22, "student_id": "S4444444"},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "User already exists"

# Test for updating a user
def test_update_user(client):
    created = _create_user(client, name="Jane", email="old@atu.ie", student_id="S5555555")
    uid = created["id"]
    r = client.put(
        f"/api/users/{uid}",
        json={"name": "Kate", "email": "new@atu.ie", "age": 26, "student_id": "S5555555"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == uid
    assert body["name"] == "Kate"
    assert body["email"] == "new@atu.ie"

# Test for deleting a user
def test_delete_user(client):
    created = _create_user(client, name="Delight", email="del@atu.ie", student_id="S7777777")
    uid = created["id"]
    r = client.delete(f"/api/users/{uid}")
    assert r.status_code == 204
    # verify deletion
    r2 = client.get(f"/api/users/{uid}")
    assert r2.status_code == 404

# Test for getting a non-existent user
def test_get_nonexistent_user(client):
    r = client.get("/api/users/999999")
    assert r.status_code == 404
    assert r.json()["detail"] == "User not found"