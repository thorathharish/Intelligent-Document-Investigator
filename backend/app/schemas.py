"""API models and the analyst-output shape. Grows with each checkpoint."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HealthResponse(BaseModel):
    ok: bool
    llm_mode: str
    model: str
    embedder: Literal["ok", "unavailable"]
    ocr: Literal["ok", "unavailable"]


class InvestigationCreate(BaseModel):
    title: str | None = None


# --- Analyst output (LLD section 10.1). Lenient where safe. ---

VALUE_TYPES = {"duration", "date", "money", "percent", "number", "boolean", "text", "none"}


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


class AnalystAspect(_Lenient):
    id: str
    label: str


class AnalystClaim(_Lenient):
    id: str = ""
    aspect: str
    evidence: str
    quote: str
    value: str = ""
    value_type: str = "text"
    scope: str | None = None
    explicit: bool = True

    @field_validator("value", mode="before")
    @classmethod
    def _value_to_str(cls, v):
        return "" if v is None else str(v)

    @field_validator("value_type", mode="before")
    @classmethod
    def _known_value_type(cls, v):
        v = str(v or "").strip().lower()
        return v if v in VALUE_TYPES else "text"


class AnalystSupersession(_Lenient):
    evidence: str
    quote: str
    aspect: str | None = None
    note: str = ""


class AnalystSentence(_Lenient):
    text: str
    claims: list[str] = Field(default_factory=list)


class AnalystOutput(_Lenient):
    aspects: list[AnalystAspect] = Field(default_factory=list)
    claims: list[AnalystClaim] = Field(default_factory=list)
    supersession: list[AnalystSupersession] = Field(default_factory=list)
    answer: list[AnalystSentence] = Field(default_factory=list)
    ambiguous: bool = False
    ambiguity_note: str | None = None


def _valid_items(model, items) -> list:
    """Keep the list entries that fit the model; discard the rest."""
    kept = []
    for item in items if isinstance(items, list) else []:
        try:
            kept.append(model.model_validate(item))
        except Exception:
            continue
    return kept


def validate_analyst_output(data: dict) -> AnalystOutput:
    """Validate the analyst's JSON. Raises ValueError when the overall shape is unusable."""
    if not isinstance(data, dict):
        raise ValueError("reply is not a JSON object")
    if not isinstance(data.get("claims", []), list) or not isinstance(data.get("aspects", []), list):
        raise ValueError('"aspects" and "claims" must be lists')
    if "claims" not in data and "aspects" not in data:
        raise ValueError('reply has neither "aspects" nor "claims"')
    return AnalystOutput(
        aspects=_valid_items(AnalystAspect, data.get("aspects")),
        claims=_valid_items(AnalystClaim, data.get("claims")),
        supersession=_valid_items(AnalystSupersession, data.get("supersession")),
        answer=_valid_items(AnalystSentence, data.get("answer")),
        ambiguous=bool(data.get("ambiguous", False)),
        ambiguity_note=data.get("ambiguity_note") if isinstance(data.get("ambiguity_note"), str) else None,
    )
