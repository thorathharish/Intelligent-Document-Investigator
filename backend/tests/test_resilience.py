"""Run cache and the LLM failure chain, end to end through the question endpoint. No network."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import settings
from app.investigation import analyst
from app.llm import openrouter
from app.llm.openrouter import OpenRouterClient
from app.main import app
from test_qa import SET_A, ScriptedLLM

LATE_FEE = [("Late fee", "late fee of 1.5% per month", "1.5%", "percent")]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _investigation(client, names=("Master_Services_Agreement.pdf", "Vendor_Payment_Policy.docx")):
    inv = client.post("/api/investigations", json={"title": "Resilience"}).json()["id"]
    client.post(f"/api/investigations/{inv}/documents",
                files=[("files", (n, (SET_A / n).read_bytes(), "application/octet-stream")) for n in names])
    return inv


@pytest.fixture()
def inv(client):
    return _investigation(client)


def _ask(client, inv, question, **body):
    response = client.post(f"/api/investigations/{inv}/questions", json={"question": question, **body})
    assert response.status_code == 200
    return response.json()


def _run_count(inv):
    return db.query_one("SELECT COUNT(*) AS n FROM runs WHERE investigation_id = ?", (inv,))["n"]


@pytest.fixture()
def scripted(monkeypatch):
    llm = ScriptedLLM(LATE_FEE)
    monkeypatch.setattr(analyst, "get_llm_client", lambda: llm)
    return llm


@pytest.fixture()
def setting():
    """Temporarily change a frozen setting."""
    saved = {}

    def change(name, value):
        saved.setdefault(name, getattr(settings, name))
        object.__setattr__(settings, name, value)

    yield change
    for name, value in saved.items():
        object.__setattr__(settings, name, value)


# --- cache ----------------------------------------------------------------------


def test_first_request_misses_and_identical_second_request_hits(client, inv, scripted):
    first = _ask(client, inv, "What is the late payment fee?")
    assert first["cached"] is False and first["state"] == "HIGH" and scripted.calls == 1

    second = _ask(client, inv, "  what is THE late   payment fee?  ")  # same question after normalisation
    assert second["cached"] is True and second["run_id"] == first["run_id"]
    assert scripted.calls == 1 and _run_count(inv) == 1  # no LLM call, no new row
    assert second["claims"] == first["claims"] and second["state"] == "HIGH"


def test_fresh_flag_bypasses_the_cache(client, inv, scripted):
    _ask(client, inv, "What is the late payment fee?")
    again = _ask(client, inv, "What is the late payment fee?", fresh=True)
    assert again["cached"] is False and scripted.calls == 2


def test_question_change_misses(client, inv, scripted):
    _ask(client, inv, "What is the late payment fee?")
    other = _ask(client, inv, "What is the late fee for overdue invoices?")
    assert other["cached"] is False and scripted.calls == 2


def test_document_change_misses(client, inv, scripted):
    _ask(client, inv, "What is the late payment fee?")
    client.post(f"/api/investigations/{inv}/documents",
                files=[("files", ("Amendment_1.pdf", (SET_A / "Amendment_1.pdf").read_bytes(), "application/pdf"))])
    after = _ask(client, inv, "What is the late payment fee?")
    assert after["cached"] is False and scripted.calls == 2


def test_model_change_misses(client, inv, scripted, setting):
    _ask(client, inv, "What is the late payment fee?")
    setting("openrouter_model", "some/other-model")
    assert _ask(client, inv, "What is the late payment fee?")["cached"] is False and scripted.calls == 2


def test_prompt_version_change_misses(client, inv, scripted, setting):
    _ask(client, inv, "What is the late payment fee?")
    setting("prompt_version", "2")
    assert _ask(client, inv, "What is the late payment fee?")["cached"] is False and scripted.calls == 2


def test_cache_is_scoped_to_the_investigation(client, inv, scripted):
    first = _ask(client, inv, "What is the late payment fee?")
    other = _ask(client, _investigation(client), "What is the late payment fee?")
    assert other["cached"] is False and other["run_id"] != first["run_id"] and scripted.calls == 2


def test_insufficient_answer_from_a_working_llm_is_cached(client, inv, monkeypatch):
    llm = ScriptedLLM([])
    monkeypatch.setattr(analyst, "get_llm_client", lambda: llm)
    first = _ask(client, inv, "What is the warranty period?")
    second = _ask(client, inv, "What is the warranty period?")
    assert first["state"] == second["state"] == "INSUFFICIENT" and second["cached"] is True and llm.calls == 1


# --- failure chain through the real adapter -------------------------------------


@pytest.fixture()
def http_llm(monkeypatch, setting):
    """Route the analyst through OpenRouterClient with a scripted HTTP transport."""
    setting("openrouter_api_key", "test-key")
    setting("llm_min_gap_s", 0)
    monkeypatch.setattr(openrouter.time, "sleep", lambda seconds: None)
    script = ScriptedLLM(LATE_FEE)

    def install(replies, mode="live"):
        calls = []

        def handler(request):
            body = json.loads(request.content)
            calls.append(body["model"])
            reply = replies[len(calls) - 1]
            if reply == "ok":
                content = json.dumps(script.build(body["messages"][1]["content"]))
                return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
            if reply == "timeout":
                raise httpx.ReadTimeout("timed out")
            if reply == "connect":
                raise httpx.ConnectError("connection refused")
            if isinstance(reply, int):
                return httpx.Response(reply, json={"error": {"message": "provider error"}}, headers={"Retry-After": "0"})
            return httpx.Response(200, json={"choices": [{"message": {"content": reply}}]})  # raw text

        client = OpenRouterClient(model="primary", fallback_models=["fallback"], mode=mode, supports_json_mode=False,
                                  http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        monkeypatch.setattr(analyst, "get_llm_client", lambda: client)
        return calls

    return install


def test_primary_success(client, inv, http_llm):
    calls = http_llm(["ok"])
    result = _ask(client, inv, "Late fee question one?")
    assert calls == ["primary"] and result["state"] == "HIGH" and result["degraded"] is False
    assert result["signals"]["llm_source"] == "live"
    assert db.query_one("SELECT model, degraded FROM runs WHERE id = ?", (result["run_id"],))["model"] == "primary"


def test_rate_limit_then_retry_succeeds(client, inv, http_llm):
    calls = http_llm([429, "ok"])
    assert _ask(client, inv, "Late fee question two?")["state"] == "HIGH" and calls == ["primary", "primary"]


def test_timeout_then_retry_then_fallback(client, inv, http_llm):
    calls = http_llm(["timeout", "timeout", "ok"])
    result = _ask(client, inv, "Late fee question three?")
    assert calls == ["primary", "primary", "fallback"] and result["state"] == "HIGH"
    assert db.query_one("SELECT model FROM runs WHERE id = ?", (result["run_id"],))["model"] == "fallback"


def test_unavailable_model_goes_straight_to_fallback(client, inv, http_llm):
    calls = http_llm([404, "ok"])
    assert _ask(client, inv, "Late fee question four?")["degraded"] is False and calls == ["primary", "fallback"]


@pytest.mark.parametrize("failure", [429, 503, "timeout", "connect"])
def test_all_models_fail_gives_evidence_only_and_is_not_cached(client, inv, http_llm, failure):
    question = f"Late fee question five {failure}?"
    calls = http_llm([failure, failure, failure])
    result = _ask(client, inv, question)
    assert calls == ["primary", "primary", "fallback"]
    assert result["degraded"] is True and result["state"] == "LOW"
    assert result["answer"] == [] and result["claims"] == [] and len(result["related"]) == 5
    assert result["signals"]["evidence_only"] is True and result["signals"]["llm_source"] == "none"
    assert result["reasons"] == ["Automatic analysis was unavailable, so only the closest passages are shown."]

    # the degraded run is not served from cache: once the model is back, the question is answered normally
    recovered = http_llm(["ok"])
    healthy = _ask(client, inv, question)
    assert healthy["cached"] is False and healthy["degraded"] is False and healthy["state"] == "HIGH"
    assert recovered == ["primary"] and _run_count(inv) == 2
    assert _ask(client, inv, question)["cached"] is True


def test_recorded_run_is_used_when_every_model_fails(client, inv, http_llm):
    http_llm(["ok"])
    _ask(client, inv, "Late fee question six?", fresh=True)
    calls = http_llm([503, 503, 503])
    result = _ask(client, inv, "Late fee question six?", fresh=True)
    assert calls == ["primary", "primary", "fallback"]
    assert result["degraded"] is False and result["state"] == "HIGH" and result["signals"]["llm_source"] == "recording"


def test_replay_mode_uses_the_recording_without_any_request(client, inv, http_llm):
    http_llm(["ok"])
    _ask(client, inv, "Late fee question seven?", fresh=True)
    calls = http_llm([], mode="replay")
    result = _ask(client, inv, "Late fee question seven?", fresh=True)
    assert calls == [] and result["state"] == "HIGH" and result["signals"]["llm_source"] == "recording"


def test_mock_mode_without_a_recording_is_evidence_only(client, inv, http_llm):
    calls = http_llm([], mode="mock")
    result = _ask(client, inv, "Late fee question eight?")
    assert calls == [] and result["degraded"] is True and result["state"] == "LOW"


def test_invalid_json_then_repair_succeeds(client, inv, http_llm):
    calls = http_llm(["I think the fee is 1.5 percent.", "ok"])
    result = _ask(client, inv, "Late fee question nine?")
    assert calls == ["primary", "primary"] and result["state"] == "HIGH" and result["degraded"] is False


def test_invalid_json_then_failed_repair_is_evidence_only(client, inv, http_llm):
    calls = http_llm(["not json", "still not json"])
    result = _ask(client, inv, "Late fee question ten?")
    assert calls == ["primary", "primary"]  # one repair attempt, no further generation
    assert result["degraded"] is True and result["state"] == "LOW" and result["claims"] == []
