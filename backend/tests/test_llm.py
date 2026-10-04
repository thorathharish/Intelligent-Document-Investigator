"""LLM adapter, tolerant JSON parsing and analyst-output validation. No network: a fake HTTP transport is used."""
import json

import httpx
import pytest

from app.config import settings
from app.investigation.analyst import _reissue_ids
from app.llm.base import LLMBadOutput, LLMUnavailable
from app.llm.json_utils import extract_json
from app.llm.openrouter import OpenRouterClient
from app.schemas import validate_analyst_output

GOOD = {
    "aspects": [{"id": "A1", "label": "Payment period"}],
    "claims": [{"id": "C1", "aspect": "A1", "evidence": "E1", "quote": "within thirty (30) days",
                "value": "30 days", "value_type": "duration", "scope": None, "explicit": True}],
    "answer": [{"text": "Payment is due within 30 days.", "claims": ["C1"]}],
}


@pytest.fixture(autouse=True)
def fast_settings():
    saved = (settings.openrouter_api_key, settings.llm_min_gap_s)
    object.__setattr__(settings, "openrouter_api_key", "test-key")
    object.__setattr__(settings, "llm_min_gap_s", 0)
    yield
    object.__setattr__(settings, "openrouter_api_key", saved[0])
    object.__setattr__(settings, "llm_min_gap_s", saved[1])


def _reply(content, status=200):
    if status != 200:
        return httpx.Response(status, json={"error": {"message": "rate limited"}}, headers={"Retry-After": "0"})
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def _client(replies, **kwargs):
    calls = []

    def handler(request):
        calls.append(json.loads(request.content)["model"])
        return replies[len(calls) - 1]

    client = OpenRouterClient(
        model="primary", fallback_models=kwargs.pop("fallbacks", ["fallback"]), mode=kwargs.pop("mode", "live"),
        supports_json_mode=False, http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    return client, calls


# --- tolerant JSON ------------------------------------------------------------


def test_extract_json_handles_fences_and_prose():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Here you go: {"a": {"b": "} tricky"}} thanks') == {"a": {"b": "} tricky"}}
    for bad in ("", "no json here", '{"a": 1', "[1, 2]"):
        with pytest.raises(ValueError):
            extract_json(bad)


def test_analyst_output_is_lenient_where_safe():
    out = validate_analyst_output(
        {"aspects": [{"id": "A1", "label": "x"}], "extra": 1,
         "claims": [{"aspect": "A1", "evidence": "E1", "quote": "q", "value": 30, "value_type": "weird"},
                    {"evidence": "E1", "quote": "no aspect"}, "not a claim"]}
    )
    assert len(out.claims) == 1 and out.claims[0].value == "30" and out.claims[0].value_type == "text"
    assert out.answer == [] and out.supersession == [] and out.ambiguous is False
    with pytest.raises(ValueError):
        validate_analyst_output({"claims": "nope", "aspects": []})
    with pytest.raises(ValueError):
        validate_analyst_output({"something": "else"})


def test_ids_are_reissued_server_side():
    out = _reissue_ids(validate_analyst_output(
        {"aspects": [{"id": "x", "label": "Fee"}],
         "claims": [{"id": "k9", "aspect": "x", "evidence": "E2", "quote": "quote text"},
                    {"id": "k3", "aspect": "missing", "evidence": "E1", "quote": "quote text"}],
         "answer": [{"text": "s", "claims": ["k9", "ghost"]}]}
    ))
    assert out.aspects[0].id == "A1"
    assert [(c.id, c.aspect, c.evidence) for c in out.claims] == [("C1", "A1", "E2"), ("C2", "", "E1")]
    assert out.answer[0].claims == ["C1"]


# --- adapter failure chain ----------------------------------------------------


def test_valid_reply_is_parsed_and_recorded():
    client, calls = _client([_reply("```json\n" + json.dumps(GOOD) + "\n```")])
    result = client.complete_json("sys valid", "user", validate_analyst_output)
    assert result.model == "primary" and not result.from_recording and calls == ["primary"]
    assert result.value.claims[0].evidence == "E1" and result.value.claims[0].quote == "within thirty (30) days"

    replay, replay_calls = _client([], mode="replay")
    again = replay.complete_json("sys valid", "user", validate_analyst_output)
    assert again.from_recording and replay_calls == []


def test_rate_limit_then_success_retries_primary_once():
    client, calls = _client([_reply("", 429), _reply(json.dumps(GOOD))])
    assert client.complete_json("sys 429", "user", validate_analyst_output).model == "primary"
    assert calls == ["primary", "primary"]


def test_primary_down_uses_fallback_model():
    client, calls = _client([_reply("", 429), _reply("", 429), _reply(json.dumps(GOOD))])
    assert client.complete_json("sys fallback", "user", validate_analyst_output).model == "fallback"
    assert calls == ["primary", "primary", "fallback"]


def test_all_models_fail_then_recording_then_error():
    ok, _ = _client([_reply(json.dumps(GOOD))])
    ok.complete_json("sys recorded", "user", validate_analyst_output)
    down, calls = _client([_reply("", 429)] * 3)
    assert down.complete_json("sys recorded", "user", validate_analyst_output).from_recording
    assert calls == ["primary", "primary", "fallback"]

    down2, _ = _client([_reply("", 429)] * 3)
    with pytest.raises(LLMUnavailable):
        down2.complete_json("sys never recorded", "user", validate_analyst_output)


def test_malformed_json_is_repaired_once():
    client, calls = _client([_reply("Sure! The answer is thirty days."), _reply(json.dumps(GOOD))])
    assert client.complete_json("sys repair", "user", validate_analyst_output).value.claims
    assert calls == ["primary", "primary"]

    bad, bad_calls = _client([_reply("still not json"), _reply("nope")])
    with pytest.raises(LLMBadOutput):
        bad.complete_json("sys bad twice", "user", validate_analyst_output)
    assert len(bad_calls) == 2


def test_mock_mode_without_recording_is_unavailable():
    client, calls = _client([], mode="mock")
    with pytest.raises(LLMUnavailable):
        client.complete_json("sys mock miss", "user", validate_analyst_output)
    assert calls == []


def test_missing_api_key_is_unavailable():
    object.__setattr__(settings, "openrouter_api_key", "")
    client, calls = _client([])
    with pytest.raises(LLMUnavailable):
        client.complete_json("sys no key", "user", validate_analyst_output)
    assert calls == []
