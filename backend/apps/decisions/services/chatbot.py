"""AI chatbot service for the freight-intelligence platform.

Design goals (see docs/CHATBOT.md, docs/SECURITY.md):

- GROUNDED: the chatbot is given ONLY real application data — the output of the
  platform's own decision engine (`evaluate_decision`) for the lane inferred from
  the question/context. It is instructed to use nothing else and never to invent
  freight rates, vessel info, port restrictions, forecasts, costs or savings.
- BACKEND-ONLY KEY: the OpenAI API key is read from settings.OPENAI["API_KEY"]
  (env OPENAI_API_KEY). It is never returned to the client and never logged.
- GRACEFUL: when no key is configured, or OpenAI errors/times out, the service
  falls back to a deterministic answer composed directly from the grounded data,
  so the endpoint always returns a useful, honest response.

Conversation context is kept in a small in-process store keyed by
conversation_id (sufficient for the prototype; swap for cache/DB later).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from django.conf import settings

from .decision_engine import (
    DecisionError,
    DecisionRequest,
    ScenarioOverrides,
    evaluate_decision,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# STRICT INDIAN SCOPE. This chatbot is specialized for overseas bulk-cargo
# procurement and vessel chartering to India's East Coast — nothing else.
# ---------------------------------------------------------------------------
PROJECT_ORIGINS = ["Australia", "Indonesia", "Mozambique", "USA", "Russia"]

# Canonical Indian East Coast destination ports, with recognised aliases so the
# intent parser matches natural phrasings (e.g. "Vizag", "Sandheads").
EAST_COAST_PORTS = [
    "Paradip", "Dhamra", "Visakhapatnam", "Gangavaram",
    "Gopalpur", "Sagar/Sandheads", "Haldia",
]
PORT_ALIASES = {
    "paradip": "Paradip",
    "dhamra": "Dhamra",
    "visakhapatnam": "Visakhapatnam",
    "vizag": "Visakhapatnam",
    "gangavaram": "Gangavaram",
    "gopalpur": "Gopalpur",
    "sagar": "Sagar/Sandheads",
    "sandheads": "Sagar/Sandheads",
    "sagar/sandheads": "Sagar/Sandheads",
    "haldia": "Haldia",
}

# In-scope vessel classes for this trade.
VESSEL_TYPES = ["Handysize", "Supramax", "Panamax", "Capesize"]

# Message shown when a question is outside the Indian freight-procurement scope.
OUT_OF_SCOPE_MESSAGE = (
    "This chatbot is specialized in overseas bulk-cargo procurement and vessel "
    "chartering for India's East Coast ports."
)

# Message shown when the required Indian data cannot be produced.
DATA_UNAVAILABLE_MESSAGE = "Indian data for this request is currently unavailable."

# Keywords that signal an in-domain (Indian freight/chartering) question.
DOMAIN_KEYWORDS = [
    "freight", "rate", "forecast", "vessel", "ship", "charter", "chartering",
    "cargo", "coal", "port", "berth", "draft", "loa", "beam", "compatib",
    "congestion", "eta", "arrival", "demurrage", "laycan", "landed", "cost",
    "contract", "spot", "voyage", "multi-voyage", "fix", "wait", "risk",
    "monsoon", "cyclone", "weather", "scenario", "tonne", "tonnes", "mt",
    "dwt", "origin", "destination", "route", "lane", "savings", "cheaper",
    "cheapest", "compare", "better", "alternative", "idle", "demand", "import",
]

SYSTEM_PROMPT = (
    "You are an AI Freight Procurement and Vessel Chartering Expert for India. "
    "You are STRICTLY specialized in overseas bulk-cargo (primarily coal) "
    "procurement and vessel chartering from Australia, Indonesia, Mozambique, "
    "the USA and Russia to India's East Coast ports (Paradip, Dhamra, "
    "Visakhapatnam, Gangavaram, Gopalpur, Sagar/Sandheads, Haldia), using "
    "Handysize, Supramax, Panamax and Capesize vessels. You are NOT a "
    "general-purpose assistant.\n\n"
    "Rules:\n"
    "1. Use ONLY the supplied application data (the JSON grounding block). NEVER "
    "compute, guess or invent freight rates, vessel details, port draft/LOA/beam "
    "limits, congestion, ETA, costs, savings, forecasts or risk scores yourself.\n"
    "2. Prioritise the Indian angle: Indian destination, Indian port/berth "
    "restrictions, Indian congestion, Indian monsoon/weather, Indian cargo "
    "demand, Indian landed cost and Indian contract strategy.\n"
    "3. Clearly label values by nature using the labels present in the data: "
    "REAL DATA, FORECAST, ESTIMATE, or SYNTHETIC DEMO DATA. Mention the data "
    "source and timestamp when the grounding provides them.\n"
    "4. Costs may be shown in INR (approximate, converted from a USD estimate) — "
    "say so.\n"
    "5. If the supplied data does not contain the answer, say exactly what is "
    "missing rather than guessing. Keep answers concise and decision-oriented."
)

# Simple in-process conversation store: conversation_id -> list of turns.
# Each turn is {"role": "user"|"assistant", "content": str}. Bounded per convo.
_CONVERSATIONS: dict[str, list[dict[str, str]]] = {}
# Last resolved lane per conversation, so follow-ups ("which is cheaper?")
# inherit the prior origin/destination/comparison.
_LANES: dict[str, dict] = {}
_MAX_TURNS = 20


@dataclass
class ChatResult:
    conversation_id: str
    answer: str
    sources: list[str] = field(default_factory=list)
    data_used: list[str] = field(default_factory=list)
    confidence: Optional[float] = None
    # Whether the phrasing came from OpenAI (True) or the grounded fallback (False).
    used_llm: bool = False

    def to_dict(self) -> dict:
        return {
            "conversation_id": self.conversation_id,
            "answer": self.answer,
            "sources": self.sources,
            "data_used": self.data_used,
            "confidence": self.confidence,
        }


# ---------------------------------------------------------------------------
# Grounding: infer the lane and retrieve REAL platform data.
# ---------------------------------------------------------------------------
def _find(text: str, options: list[str]) -> Optional[str]:
    for o in options:
        if o.lower() in text:
            return o
    return None


def _find_ports(text: str) -> list[str]:
    """Return canonical Indian ports mentioned in the text (via aliases), in
    first-seen order and de-duplicated."""
    found: list[str] = []
    for alias, canonical in PORT_ALIASES.items():
        if alias in text and canonical not in found:
            # Record the position so we can order by appearance.
            found.append(canonical)
    # Order by where each canonical port's earliest alias appears.
    def _pos(canonical: str) -> int:
        return min(
            (text.find(a) for a, c in PORT_ALIASES.items() if c == canonical and a in text),
            default=10_000,
        )
    return sorted(found, key=_pos)


def _find_vessel_type(text: str) -> Optional[str]:
    for vt in VESSEL_TYPES:
        if vt.lower() in text:
            return vt
    return None


def _is_in_scope(message: str, context: dict) -> bool:
    """True if the question is about Indian bulk-cargo freight/chartering.

    A question is in-scope if it mentions an in-scope origin, an Indian port, a
    vessel class, or any domain keyword — or if page context already pins a lane
    (the user is on a cargo/route/forecast page). Everything else is rejected.
    """
    q = message.lower()
    if context and (context.get("origin") or context.get("destination")):
        return True
    if _find(q, PROJECT_ORIGINS):
        return True
    if _find_ports(q):
        return True
    if _find_vessel_type(q):
        return True
    if "india" in q or "indian" in q:
        return True
    return any(kw in q for kw in DOMAIN_KEYWORDS)


def _extract_pct(text: str) -> Optional[float]:
    import re

    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    return float(m.group(1)) if m else None


def _extract_tonnes(text: str) -> Optional[Decimal]:
    """Parse a cargo quantity like '100000 MT', '100,000 mt', or '75000 tonnes'."""
    import re

    m = re.search(r"([\d,]{3,})\s*(?:mt|t|tonne|tonnes|dwt)\b", text, re.IGNORECASE)
    if not m:
        return None
    try:
        return Decimal(m.group(1).replace(",", ""))
    except Exception:
        return None


def _dec(value: Any, default: Optional[Decimal] = None) -> Optional[Decimal]:
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value))
    except Exception:
        return default


def _resolve_lane(message: str, context: dict, prev_lane: Optional[dict] = None) -> dict:
    """Infer origin/destination/commodity/quantity/vessel from the message,
    page context and the previous turn's lane (for follow-ups).

    Precedence: explicit page `context` > values parsed from this message >
    the previous lane (so "which is cheaper?" keeps the earlier comparison) >
    the documented demo default. Nothing is invented.
    """
    q = message.lower()
    ctx = context or {}
    prev = prev_lane or {}

    origin = ctx.get("origin") or _find(q, PROJECT_ORIGINS) or prev.get("origin") or "Australia"

    ports_in_q = _find_ports(q)
    destination = (
        ctx.get("destination")
        or (ports_in_q[0] if ports_in_q else None)
        or prev.get("destination")
        or "Paradip"
    )

    commodity = ctx.get("commodity") or prev.get("commodity") or "Coal"
    cargo = _dec(ctx.get("cargo_quantity")) or _extract_tonnes(q) or _dec(prev.get("cargo_tonnes")) or Decimal("75000")
    vessel_type = _find_vessel_type(q) or prev.get("vessel_type")

    # A comparison of two origins to one port ("compare Australia and Indonesia").
    origins_in_q = [o for o in PROJECT_ORIGINS if o.lower() in q]
    compare_origins = origins_in_q if len(origins_in_q) >= 2 else prev.get("compare_origins")

    # Optional scenario: "what if freight/congestion increases/decreases N% / doubles".
    pct = _extract_pct(q)
    freight_change = None
    if pct is not None and ("freight" in q or "rate" in q or "increase" in q or "decrease" in q):
        freight_change = -pct if any(w in q for w in ("decrease", "fall", "drop")) else pct

    return {
        "origin": origin,
        "destination": destination,
        "commodity": commodity,
        "cargo_tonnes": cargo,
        "vessel_type": vessel_type,
        "ports_in_q": ports_in_q,
        "compare_origins": compare_origins,
        "freight_change_pct": freight_change,
    }


def _grounded_data(lane: dict) -> dict:
    """Retrieve REAL platform data for the inferred lane via the decision engine.

    Returns the composed decision dict (freight forecast, vessel, compatibility,
    congestion, ETA, demurrage, landed cost, contract, risk, FIX/WAIT, savings,
    explainability). Raises DecisionError on invalid inputs.
    """
    laycan_start = date.today() + timedelta(days=14)
    laycan_end = laycan_start + timedelta(days=10)
    scenario = ScenarioOverrides(freight_change_pct=lane["freight_change_pct"])
    req = DecisionRequest(
        commodity=lane["commodity"],
        cargo_tonnes=lane["cargo_tonnes"],
        origin=lane["origin"],
        destination=lane["destination"],
        laycan_start=laycan_start,
        laycan_end=laycan_end,
        scenario=scenario,
    )
    return evaluate_decision(req).to_dict()


def _compact_grounding(decision: dict, lane: dict) -> dict:
    """A small, LLM-friendly subset of the decision — only fields we will let the
    model speak to. Keeps the prompt tight and avoids leaking unrelated data."""
    v = decision.get("recommended_vessel") or {}
    fc = decision.get("freight_forecast") or {}
    risk = decision.get("risk") or {}
    contract = decision.get("recommended_contract") or {}
    timing = decision.get("timing") or {}

    # Data label for the freight figure: a stored forecast is FORECAST (from a
    # model); the planning default is SYNTHETIC DEMO DATA. Others are ESTIMATE.
    fc_source = fc.get("source")
    freight_label = "FORECAST" if fc_source == "FreightForecast" else "SYNTHETIC DEMO DATA"

    return {
        "india_scope": True,
        "lane": {"origin": lane["origin"], "destination": lane["destination"],
                 "commodity": lane["commodity"], "cargo_tonnes": str(lane["cargo_tonnes"]),
                 "vessel_type_requested": lane.get("vessel_type"),
                 "compare_origins": lane.get("compare_origins")},
        "data_labels": {
            "freight_forecast": freight_label,
            "vessel_recommendation": "ESTIMATE",
            "compatibility": "REAL DATA (rule-based over stored vessel/berth data)",
            "congestion": "ESTIMATE",
            "eta": "ESTIMATE",
            "demurrage": "ESTIMATE",
            "total_landed_cost": "ESTIMATE (USD; shown in INR is approximate)",
            "risk": "ESTIMATE",
        },
        "freight_forecast": {
            "band": fc.get("band"),
            "working_rate_per_tonne_usd": fc.get("working_rate"),
            "source": fc_source,
            "label": freight_label,
            "generated_at": fc.get("generated_at"),
            "model": fc.get("freight_model"),
            "model_version": fc.get("freight_model_version"),
        },
        "recommended_vessel": {
            "name": v.get("vessel_name"),
            "type": v.get("vessel_type"),
            "suitability_score": v.get("suitability_score"),
        } if v else None,
        "compatibility": decision.get("compatibility"),
        "congestion": decision.get("congestion"),
        "eta": decision.get("eta"),
        "demurrage_usd": decision.get("demurrage"),
        "total_landed_cost_usd": decision.get("total_landed_cost"),
        "recommended_contract": {
            "strategy": contract.get("recommended_strategy"),
            "reason": contract.get("reason"),
        },
        "risk": {"overall_score": risk.get("overall_score"), "level": risk.get("risk_level")},
        "timing_decision": decision.get("timing_decision"),
        "timing_reason": timing.get("reason"),
        "expected_savings_usd": decision.get("expected_savings"),
        "confidence": decision.get("confidence"),
        "explainability": {
            "reasons": (decision.get("explainability") or {}).get("reasons"),
            "positive_factors": (decision.get("explainability") or {}).get("positive_factors"),
            "negative_factors": (decision.get("explainability") or {}).get("negative_factors"),
        },
        "data_freshness": (decision.get("explainability") or {}).get("data_freshness"),
    }


def _fallback_answer(decision: dict, lane: dict) -> str:
    """A deterministic, grounded answer used when OpenAI is unavailable. India-
    framed and label-aware; every value comes from the platform engines."""
    origin, dest = lane["origin"], lane["destination"]
    timing = decision.get("timing_decision", "MONITOR")
    reason = (decision.get("timing") or {}).get("reason", "")
    v = decision.get("recommended_vessel") or {}
    fc = decision.get("freight_forecast") or {}
    contract = (decision.get("recommended_contract") or {}).get("recommended_strategy")
    risk = decision.get("risk") or {}
    congestion = decision.get("congestion") or {}

    parts = [f"For {origin} → {dest} (East Coast India, {lane['commodity']}): recommended action is {timing}."]
    if reason:
        parts.append(reason)
    if fc.get("working_rate"):
        label = "FORECAST" if fc.get("source") == "FreightForecast" else "SYNTHETIC DEMO DATA"
        gen = f", as of {fc.get('generated_at')}" if fc.get("generated_at") else ""
        parts.append(f"Working freight rate: {fc['working_rate']}/t USD ({label}{gen}).")
    if v:
        parts.append(
            f"Recommended vessel: {v.get('vessel_name')} ({v.get('vessel_type')}), "
            f"suitability {float(v.get('suitability_score', 0)):.0f}/100 (ESTIMATE)."
        )
    if congestion.get("score") is not None:
        parts.append(f"{dest} congestion: {float(congestion['score']):.0f}/100 (ESTIMATE).")
    if contract:
        parts.append(f"Contract: {contract} (lowest risk-adjusted cost, ESTIMATE).")
    if risk:
        parts.append(f"Overall risk {float(risk.get('overall_score', 0)):.0f}/100 ({risk.get('risk_level')}, ESTIMATE).")
    parts.append("(Grounded answer from the platform engines; OpenAI phrasing unavailable.)")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# OpenAI (Responses API) — lazy, timeout-guarded, key never logged.
# ---------------------------------------------------------------------------
def _openai_phrase(message: str, grounding: dict, history: list[dict[str, str]]) -> Optional[str]:
    """Ask OpenAI to phrase an answer using ONLY the grounded data. Returns the
    text, or None if OpenAI is not configured or the call fails (caller then
    uses the deterministic fallback). The API key is never logged."""
    api_key = settings.OPENAI.get("API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI  # lazy import; optional dependency
    except ImportError:
        logger.warning("openai SDK not installed; using grounded fallback.")
        return None

    import json

    cfg = settings.OPENAI
    # Build the input: system role + prior turns + the grounded data + question.
    convo_lines = "\n".join(f"{t['role']}: {t['content']}" for t in history[-6:])
    grounded_json = json.dumps(grounding, default=str)
    user_block = (
        (f"Conversation so far:\n{convo_lines}\n\n" if convo_lines else "")
        + "Application data you MUST ground your answer in (JSON):\n"
        + grounded_json
        + f"\n\nUser question: {message}"
    )

    try:
        client = OpenAI(api_key=api_key, timeout=cfg.get("TIMEOUT", 20.0))
        resp = client.responses.create(
            model=cfg.get("MODEL", "gpt-4o-mini"),
            instructions=SYSTEM_PROMPT,
            input=user_block,
            max_output_tokens=cfg.get("MAX_OUTPUT_TOKENS", 600),
        )
        text = getattr(resp, "output_text", None)
        if text:
            return text.strip()
        logger.warning("OpenAI returned no output_text; using grounded fallback.")
        return None
    except Exception as exc:  # never leak the key; log only the error type/message
        logger.warning("OpenAI call failed (%s); using grounded fallback.", type(exc).__name__)
        return None


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------
def answer_chat(
    message: str,
    conversation_id: Optional[str] = None,
    context: Optional[dict] = None,
) -> ChatResult:
    """Answer a chat message, grounded in real platform data.

    Always returns a ChatResult: OpenAI phrasing when configured/available,
    otherwise a deterministic grounded fallback. Raises DecisionError only for
    genuinely invalid grounding inputs (the caller maps that to HTTP 400).
    """
    conversation_id = conversation_id or str(uuid.uuid4())
    history = _CONVERSATIONS.setdefault(conversation_id, [])
    prev_lane = _LANES.get(conversation_id)

    # 1. Scope gate: reject anything outside Indian bulk-cargo freight/chartering.
    #    A follow-up on an existing conversation lane stays in scope.
    if not _is_in_scope(message, context or {}) and prev_lane is None:
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": OUT_OF_SCOPE_MESSAGE})
        return ChatResult(
            conversation_id=conversation_id,
            answer=OUT_OF_SCOPE_MESSAGE,
            sources=[],
            data_used=[],
            confidence=None,
            used_llm=False,
        )

    lane = _resolve_lane(message, context or {}, prev_lane)

    # 2. Grounding: real platform data only. If it can't be produced, be honest.
    try:
        decision = _grounded_data(lane)
    except DecisionError:
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": DATA_UNAVAILABLE_MESSAGE})
        return ChatResult(
            conversation_id=conversation_id,
            answer=DATA_UNAVAILABLE_MESSAGE,
            sources=[],
            data_used=[],
            confidence=None,
            used_llm=False,
        )

    grounding = _compact_grounding(decision, lane)
    # Remember the lane for the next follow-up in this conversation.
    _LANES[conversation_id] = lane

    llm_text = _openai_phrase(message, grounding, history)
    used_llm = llm_text is not None
    answer_text = llm_text or _fallback_answer(decision, lane)

    # Record the turn (bounded).
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer_text})
    if len(history) > _MAX_TURNS:
        del history[: len(history) - _MAX_TURNS]

    # `sources` = the platform engines that produced the grounding.
    sources = [
        "freight_forecast", "vessel_recommendation", "vessel_port_compatibility",
        "port_congestion", "eta", "voyage_cost", "landed_cost",
        "contract_strategy", "risk", "fix_wait",
    ]
    # `data_used` = which grounded fields were actually populated (non-null).
    data_used = [k for k, val in grounding.items() if val not in (None, {}, [])]

    return ChatResult(
        conversation_id=conversation_id,
        answer=answer_text,
        sources=sources,
        data_used=data_used,
        # Confidence is the platform's own decision confidence (or null).
        confidence=decision.get("confidence"),
        used_llm=used_llm,
    )


def reset_conversation(conversation_id: str) -> None:
    _CONVERSATIONS.pop(conversation_id, None)
    _LANES.pop(conversation_id, None)
