"""Deployment: only configured frontend origins may call the API from a browser."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.api import demo
from app.config import Settings


def test_allowed_origins_setting(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", " https://investigator.example.app/ , http://localhost:4173 ")
    assert Settings().allowed_origins == ["https://investigator.example.app", "http://localhost:4173"]
    monkeypatch.setenv("ALLOWED_ORIGINS", "")
    assert Settings().allowed_origins == []


def test_cors_allows_the_configured_origin_only():
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["https://investigator.example.app"],
                       allow_methods=["GET", "POST"], allow_headers=["*"])
    app.include_router(demo.router, prefix="/api")
    client = TestClient(app)

    allowed = client.get("/api/health", headers={"Origin": "https://investigator.example.app"})
    assert allowed.headers["access-control-allow-origin"] == "https://investigator.example.app"
    other = client.get("/api/health", headers={"Origin": "https://somewhere-else.example"})
    assert "access-control-allow-origin" not in other.headers

    preflight = client.options("/api/health", headers={
        "Origin": "https://investigator.example.app", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"})
    assert preflight.status_code == 200 and "POST" in preflight.headers["access-control-allow-methods"]
