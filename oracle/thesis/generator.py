"""
Betting Thesis Generator — Week 25D/25E.

Reads match_betting_cards.json (from oracle.pipeline.betting) and optionally
knowledge_activations.json (from oracle.pipeline.knowledge) to produce
knowledge-enriched BettingThesis objects.

Stage 1 scope:
  - Markets: 1x2, double_chance, draw_no_bet, over_under_2_5, btts,
    correct_score (top 1)
  - Causal chains and game scripts populated from knowledge layer (25E)
  - No player props, cards, corners, shots (Stage 2)
  - Market data where available (currently limited to 4 dummy matches)
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from oracle.thesis.contrarian import classify_contrarian, raw_edge
from oracle.thesis.ranking import no_opportunity_reason, rank_theses
from oracle.thesis.schema import (
    BettingThesis,
    MatchThesisSummary,
    DATA_STAGE,
    MODEL_VERSION,
    PRIMARY_MARKETS,
)
from oracle.thesis.scoring import assign_display_tier, compute_opportunity_score
from oracle.thesis.templates import build_explanation

log = logging.getLogger(__name__)

_ARTIFACTS = Path("data/artifacts")

# Forbidden terms to screen from knowledge-enriched text (mirrors schema.FORBIDDEN_TERMS)
_FORBIDDEN = frozenset({
    "bet this", "lock", "guaranteed", "sure thing", "profit",
    "free money", "must bet", "bet this now", "risk-free",
})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _thesis_id(match_id: str, market_type: str, selection: str) -> str:
    key = f"{match_id}:{market_type}:{selection}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def _load_knowledge_activations() -> dict[str, dict]:
    """Load knowledge_activations.json keyed by match_id. Returns {} if missing."""
    path = _ARTIFACTS / "knowledge_activations.json"
    try:
        rows = json.loads(path.read_text())
        return {r["match_id"]: r for r in rows if "match_id" in r}
    except FileNotFoundError:
        return {}
    except Exception as exc:
        log.warning("Could not load knowledge_activations.json: %s", exc)
        return {}


def _load_knowledge_weights() -> dict:
    """
    Load effective weights for knowledge components.

    Prefers knowledge_effective_weights.json (learning system output, Week 27)
    over knowledge_weights.json (static calibration, Week 26).
    Returns empty dict (all neutral) if neither exists.
    """
    for filename in ("knowledge_effective_weights.json", "knowledge_weights.json"):
        path = _ARTIFACTS / filename
        try:
            data = json.loads(path.read_text())
            log.debug("Loaded weights from %s", filename)
            return data
        except FileNotFoundError:
            continue
        except Exception as exc:
            log.warning("Could not load %s: %s", filename, exc)
    return {}


def _chain_weight(weights: dict, chain_id: str) -> float:
    return float(weights.get("chains", {}).get(chain_id, 1.0))


def _script_weight(weights: dict, script_id: str) -> float:
    return float(weights.get("scripts", {}).get(script_id, 1.0))


def _safe_text(text: str) -> str:
    """Strip any forbidden terms from knowledge-injected text."""
    lowered = text.lower()
    for term in _FORBIDDEN:
        if term in lowered:
            text = text.replace(term, "[redacted]")
    return text


def _knowledge_supports_market(activation: dict, market_type: str) -> bool:
    """Return True if any activated chain or top script affects this market."""
    mkt = market_type.lower()
    for chain in activation.get("activated_chains", []):
        for m in chain.get("markets_affected", []):
            if mkt in m.lower():
                return True
    for script in activation.get("activated_scripts", [])[:2]:
        for m in script.get("markets_impacted", {}).keys():
            if mkt in m.lower():
                return True
    return False


def _enrich_thesis_with_knowledge(
    thesis: BettingThesis,
    activation: dict,
    weights: Optional[dict] = None,
) -> None:
    """
    Mutate thesis in-place to add football knowledge context.

    Populates:
        active_causal_chains — from activated_chains
        active_game_scripts  — from activated_scripts[:3]
        supporting_factors   — adds chain factors
        counter_factors      — adds knowledge counter context
        human_body           — appends knowledge body paragraph
        confidence_score     — ±0.10 max, weighted by calibration weights (Week 26)

    Knowledge is context + confidence modifier only; probability is unchanged.
    Maximum confidence impact is capped at ±0.10 to prevent knowledge dominating.
    """
    if weights is None:
        weights = {}
    chains  = activation.get("activated_chains", [])
    scripts = activation.get("activated_scripts", [])[:3]
    k_conf  = activation.get("knowledge_confidence", 0.0)

    # 1. Populate active_causal_chains
    if chains:
        thesis.active_causal_chains = json.dumps([
            {
                "chain_id":   c["chain_id"],
                "name":       c["name"],
                "markets_affected": c.get("markets_affected", []),
            }
            for c in chains
        ])

    # 2. Populate active_game_scripts
    if scripts:
        thesis.active_game_scripts = json.dumps([
            {
                "script_id":    s["script_id"],
                "display_name": s["display_name"],
                "probability":  s["probability"],
            }
            for s in scripts
        ])

    # 3. Enrich supporting_factors with chain-level factors
    chain_factors = [
        {
            "factor_type": "causal_chain",
            "factor_id":   f"chain:{c['chain_id']}",
            "description": c.get("explanation_snippet", c["name"]),
            "weight":      round(c.get("activation_confidence", 0.65), 3),
            "confidence":  round(k_conf, 3),
        }
        for c in chains[:2]
    ]
    if chain_factors:
        existing = json.loads(thesis.supporting_factors)
        thesis.supporting_factors = json.dumps(existing + chain_factors)

    # 4. Enrich counter_factors with knowledge counter context
    counter_ctx = activation.get("counter_context", [])
    if counter_ctx:
        existing = json.loads(thesis.counter_factors)
        knowledge_counter = [{
            "factor_type": "knowledge_counter",
            "factor_id":   "knowledge:counter_context",
            "description": _safe_text(counter_ctx[0]),
            "weight":      0.50,
            "confidence":  round(k_conf, 3),
        }]
        thesis.counter_factors = json.dumps(existing + knowledge_counter)

    # 5. Append knowledge body to human_body (safe text only)
    k_body = _safe_text(activation.get("knowledge_body", ""))
    if k_body and len(k_body) > 20:
        separator = " " if thesis.human_body.endswith(".") else ". "
        thesis.human_body = thesis.human_body + separator + k_body

    # 6. Confidence adjustment — weight-adjusted, capped at ±0.10 (Week 26)
    # Base adjustment is ±0.05; multiplied by mean calibration weight of
    # activated chains. Top script weight provides secondary modifier.
    # Total adjustment is hard-capped at ±0.10 so knowledge never dominates.
    _MAX_KNOWLEDGE_ADJUSTMENT = 0.10

    supports = _knowledge_supports_market(activation, thesis.market_type)
    if k_conf >= 0.50:
        direction = 1.0 if supports else -1.0

        # Compute mean chain weight (default 1.0 = neutral)
        chain_weights = [_chain_weight(weights, c["chain_id"]) for c in chains]
        mean_chain_w  = (sum(chain_weights) / len(chain_weights)) if chain_weights else 1.0

        # Top script weight as secondary modifier (capped contribution)
        top_script_w = 1.0
        if scripts:
            top_script_w = _script_weight(weights, scripts[0]["script_id"])

        # Weighted delta: base 0.05 × geometric mean of chain+script weights
        import math as _math
        combined_weight = _math.sqrt(mean_chain_w * top_script_w)
        base_delta   = 0.05 * combined_weight
        # Cap total at ±0.10
        capped_delta = max(-_MAX_KNOWLEDGE_ADJUSTMENT,
                           min(_MAX_KNOWLEDGE_ADJUSTMENT, direction * base_delta))

        new_conf = round(max(0.0, min(1.0, thesis.confidence_score + capped_delta)), 3)
        thesis.confidence_score = new_conf
        # Update label to match
        if new_conf >= 0.80:
            thesis.confidence_label = "very_high"
        elif new_conf >= 0.65:
            thesis.confidence_label = "high"
        elif new_conf >= 0.50:
            thesis.confidence_label = "medium"
        elif new_conf >= 0.35:
            thesis.confidence_label = "low"
        else:
            thesis.confidence_label = "very_low"


def _load_betting_cards() -> list[dict]:
    path = _ARTIFACTS / "match_betting_cards.json"
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        log.warning("match_betting_cards.json not found — run 'make betting' first")
        return []
    except Exception as exc:
        log.error("Failed to load match_betting_cards.json: %s", exc)
        return []


def _market_quality(market: dict) -> str:
    dq = market.get("data_quality", "model_only")
    if dq == "complete" and market.get("market_probability") is not None:
        return "sufficient"
    if dq == "model_only":
        return "unavailable"
    return "thin"


def _supporting_factors_json(
    market_type: str,
    model_source: str,
    has_market_data: bool,
) -> str:
    factors = []
    if model_source in ("elo_blend", "dixon_coles", "dc_grid"):
        factors.append({
            "factor_type": "feature",
            "factor_id": f"model:{model_source}",
            "description": f"Oracle {model_source.replace('_', ' ')} model probability estimate.",
            "weight": 0.70,
            "confidence": 0.65,
        })
    if has_market_data:
        factors.append({
            "factor_type": "market_drift",
            "factor_id": "market:implied_probability",
            "description": "Market implied probability available for direct comparison.",
            "weight": 0.30,
            "confidence": 0.80,
        })
    return json.dumps(factors)


def _counter_factors_json(has_market_data: bool) -> str:
    factors = []
    if not has_market_data:
        factors.append({
            "factor_type": "feature",
            "factor_id": "data:no_market_benchmark",
            "description": "No market benchmark available. Model estimate unvalidated.",
            "weight": 0.80,
            "confidence": 1.0,
        })
    factors.append({
        "factor_type": "feature",
        "factor_id": "data:stage1_limitation",
        "description": (
            "Stage 1 model lacks player availability, recent form details, "
            "and tactical context that may be reflected in market prices."
        ),
        "weight": 0.40,
        "confidence": 0.90,
    })
    return json.dumps(factors)


# ── Per-market thesis builder ─────────────────────────────────────────────────

def _build_thesis(
    match_id: str,
    home_team: str,
    away_team: str,
    market: dict,
    generated_at: str,
) -> Optional[BettingThesis]:
    """Build one BettingThesis from a BetMarketProbability dict."""
    market_type = market.get("market_type", "")
    selection   = market.get("selection", "")

    # Only generate for primary markets
    if market_type not in PRIMARY_MARKETS:
        return None

    # For correct_score: only include top 1 (highest probability scoreline)
    # Generator will deduplicate later — mark them and keep only top-prob one

    model_prob = market.get("probability")
    if model_prob is None:
        return None

    mq = _market_quality(market)
    market_implied = market.get("market_probability") if mq == "sufficient" else None

    edge = raw_edge(model_prob, market_implied)
    edge_pct = round(edge * 100, 2) if edge is not None else None

    classification, contrarian_score = classify_contrarian(model_prob, market_implied)

    fair_odds_val = round(1.0 / model_prob, 4) if model_prob > 0 else 0.0

    # Line for O/U markets
    line: Optional[float] = None
    if "_1_5" in market_type:
        line = 1.5
    elif "_2_5" in market_type:
        line = 2.5
    elif "_3_5" in market_type:
        line = 3.5

    score, confidence, confidence_label, risk_level = compute_opportunity_score(
        market_type=market_type,
        model_probability=model_prob,
        market_implied_probability=market_implied,
        contrarian_classification=classification,
        market_quality=mq,
    )

    display_tier = assign_display_tier(score, classification, model_prob)

    headline, body, key_risk = build_explanation(
        market_type=market_type,
        selection=selection,
        line=line,
        model_probability=model_prob,
        market_implied_probability=market_implied,
        raw_edge=edge,
        contrarian_classification=classification,
        home_team=home_team,
        away_team=away_team,
        confidence_label=confidence_label,
    )

    model_source = market.get("model_source", "elo_blend")
    has_market_data = market_implied is not None

    try:
        return BettingThesis(
            thesis_id=_thesis_id(match_id, market_type, selection),
            match_id=match_id,
            generated_at=generated_at,
            model_version=MODEL_VERSION,
            data_stage=DATA_STAGE,
            market_type=market_type,
            selection=selection,
            line=line,
            model_probability=round(model_prob, 4),
            market_implied_probability=(
                round(market_implied, 4) if market_implied is not None else None
            ),
            raw_edge=edge,
            edge_pct=edge_pct,
            fair_odds=fair_odds_val,
            market_quality=mq,
            contrarian_classification=classification,
            contrarian_score=contrarian_score,
            confidence_score=confidence,
            confidence_label=confidence_label,
            risk_level=risk_level,
            supporting_factors=_supporting_factors_json(market_type, model_source, has_market_data),
            counter_factors=_counter_factors_json(has_market_data),
            active_game_scripts=json.dumps([]),   # Stage 2
            active_causal_chains=json.dumps([]),  # Stage 2
            human_headline=headline,
            human_body=body,
            key_risk_statement=key_risk,
            opportunity_score=score,
            rank=0,
            display_tier=display_tier,
        )
    except AssertionError as exc:
        log.warning("Language/schema violation in thesis %s/%s/%s: %s", match_id, market_type, selection, exc)
        return None


# ── Match-level generator ─────────────────────────────────────────────────────

def generate_match_theses(
    card: dict,
    generated_at: str,
    knowledge_activation: Optional[dict] = None,
    knowledge_weights: Optional[dict] = None,
) -> tuple[list[BettingThesis], MatchThesisSummary]:
    """
    Generate, rank, and summarise theses for one match.

    Parameters
    ----------
    card:                 MatchBettingCard dict.
    generated_at:         ISO timestamp string.
    knowledge_activation: Optional KnowledgeActivation.to_dict() for this match.

    Returns (theses_ranked, summary).
    """
    match_id  = card["match_id"]
    home_team = card.get("home_team", "")
    away_team = card.get("away_team", "")
    group     = card.get("group", "")
    markets   = card.get("markets", [])

    # Filter to primary markets only, deduplicate correct_score to top-prob
    theses: list[BettingThesis] = []
    best_cs_prob: float = -1.0
    best_cs_thesis: Optional[BettingThesis] = None

    for mkt in markets:
        t = _build_thesis(match_id, home_team, away_team, mkt, generated_at)
        if t is None:
            continue
        if t.market_type == "correct_score":
            # Keep only highest-probability scoreline
            if t.model_probability > best_cs_prob:
                best_cs_prob = t.model_probability
                best_cs_thesis = t
        else:
            theses.append(t)

    if best_cs_thesis is not None:
        theses.append(best_cs_thesis)

    # Enrich with knowledge before ranking (enrichment affects confidence scores)
    _weights = knowledge_weights or {}
    if knowledge_activation:
        for t in theses:
            try:
                _enrich_thesis_with_knowledge(t, knowledge_activation, _weights)
            except Exception as exc:
                log.warning(
                    "Knowledge enrichment failed for %s/%s: %s",
                    match_id, t.market_type, exc,
                )
        if best_cs_thesis is not None:
            try:
                _enrich_thesis_with_knowledge(best_cs_thesis, knowledge_activation, _weights)
            except Exception:
                pass

    # Rank with diversification
    theses = rank_theses(theses)

    has_market_data = any(
        t.market_quality == "sufficient" for t in theses
    )

    n_featured   = sum(1 for t in theses if t.display_tier == "featured")
    n_secondary  = sum(1 for t in theses if t.display_tier == "secondary")
    n_watchlist  = sum(1 for t in theses if t.display_tier == "watchlist")
    n_hidden     = sum(1 for t in theses if t.display_tier == "hidden")
    top_score    = max((t.opportunity_score for t in theses), default=0)

    displayed = [t for t in theses if t.rank >= 1]
    no_opp_reason = no_opportunity_reason(theses, has_market_data) if not displayed else ""

    top_thesis_dict = displayed[0].to_dict() if displayed else None

    summary = MatchThesisSummary(
        match_id=match_id,
        home_team=home_team,
        away_team=away_team,
        group=group,
        n_theses_generated=len(theses),
        n_featured=n_featured,
        n_secondary=n_secondary,
        n_watchlist=n_watchlist,
        n_hidden=n_hidden,
        top_opportunity_score=top_score,
        has_market_data=has_market_data,
        no_opportunity_reason=no_opp_reason,
        top_thesis=top_thesis_dict,
        generated_at=generated_at,
    )

    return theses, summary


# ── All-matches generator ─────────────────────────────────────────────────────

def generate_all_theses() -> tuple[list[BettingThesis], list[MatchThesisSummary]]:
    """
    Generate theses for all 72 matches, enriched with knowledge layer when available.

    Returns (all_theses, match_summaries).
    """
    cards = _load_betting_cards()
    if not cards:
        log.error("No betting cards found. Cannot generate theses.")
        return [], []

    knowledge_by_match = _load_knowledge_activations()
    if knowledge_by_match:
        log.info("Knowledge layer available for %d matches", len(knowledge_by_match))
    else:
        log.info("No knowledge activations found — theses will be model-only")

    # Load calibration weights (Week 26) — neutral (1.0) if not yet generated
    kweights = _load_knowledge_weights()
    if kweights:
        log.info("Knowledge calibration weights loaded")

    generated_at = datetime.now(timezone.utc).isoformat()
    all_theses: list[BettingThesis] = []
    all_summaries: list[MatchThesisSummary] = []

    for card in cards:
        match_id = card.get("match_id")
        knowledge = knowledge_by_match.get(match_id)
        try:
            theses, summary = generate_match_theses(card, generated_at, knowledge, kweights)
            all_theses.extend(theses)
            all_summaries.append(summary)
        except Exception as exc:
            log.error("Failed to generate theses for %s: %s", match_id, exc)

    n_enriched = sum(
        1 for t in all_theses
        if json.loads(t.active_causal_chains)
    )
    log.info(
        "Generated %d theses for %d matches (%d knowledge-enriched)",
        len(all_theses), len(all_summaries), n_enriched,
    )
    return all_theses, all_summaries
