"""
Market Intelligence Pipeline — Week 28.

Generates MarketIntelligenceCard objects for corners, cards, and shots
for every match that has knowledge activation data.

Artifacts written:
    market_intelligence_cards.json
    market_intelligence_summary.json
    market_intelligence.parquet        (optional — skipped if polars unavailable)

Pipeline order:
    knowledge → knowledge_calibration → knowledge_learning
    → market_intelligence → thesis → export-web
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "data" / "artifacts"


def _load_json(path: Path, fallback: object = None) -> object:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return fallback if fallback is not None else []
    except Exception as exc:
        log.warning("Could not load %s: %s", path.name, exc)
        return fallback if fallback is not None else []


def _build_card(
    match_id: str,
    market_type: str,
    activation: dict,
    home_team: str,
    away_team: str,
    home_profile: Optional[dict],
    away_profile: Optional[dict],
    effective_weights: Optional[dict],
    trend_map: dict[str, str],
    generated_at: str,
) -> "MarketIntelligenceCard":  # type: ignore[name-defined]
    from oracle.market_intelligence.corners  import analyze_corners
    from oracle.market_intelligence.cards    import analyze_cards
    from oracle.market_intelligence.shots    import analyze_shots
    from oracle.market_intelligence.signals  import classify_signal, classify_risk
    from oracle.market_intelligence.scoring  import compute_knowledge_confidence, apply_learning_trend, score_to_confidence
    from oracle.market_intelligence.explain  import build_explanation
    from oracle.market_intelligence.schema   import MarketIntelligenceCard

    # ── 1. Market-specific analysis ───────────────────────────────────────────
    if market_type == "corners":
        analysis = analyze_corners(activation, home_profile, away_profile, effective_weights)
    elif market_type == "cards":
        analysis = analyze_cards(activation, home_profile, away_profile, effective_weights)
    else:
        analysis = analyze_shots(activation, home_profile, away_profile, effective_weights)

    # ── 2. Confidence ─────────────────────────────────────────────────────────
    base_conf = score_to_confidence(
        analysis.score,
        len(analysis.supporting_mechanisms),
        data_quality="seed",
    )
    kc = compute_knowledge_confidence(activation, effective_weights, base_conf)
    kc = apply_learning_trend(kc, analysis.active_chains, analysis.active_scripts, trend_map)

    knowledge_conf = float(activation.get("knowledge_confidence", 0.30))

    # ── 3. Signal + risk ──────────────────────────────────────────────────────
    signal_level, display_tier = classify_signal(
        analysis.score, analysis.direction, kc, "seed"
    )
    risk_level = classify_risk(analysis.score, kc, len(analysis.counter_mechanisms))

    # ── 4. Explanation ────────────────────────────────────────────────────────
    home_arch = activation.get("home_archetype", "unknown")
    away_arch = activation.get("away_archetype", "unknown")
    headline, explanation, key_risk = build_explanation(
        market_type=market_type,
        direction=analysis.direction,
        environment=analysis.environment,
        supporting_mechanisms=analysis.supporting_mechanisms,
        counter_mechanisms=analysis.counter_mechanisms,
        home_archetype=home_arch,
        away_archetype=away_arch,
        home_team=home_team,
        away_team=away_team,
        active_scripts=analysis.active_scripts,
    )

    return MarketIntelligenceCard(
        match_id=match_id,
        market_type=market_type,
        signal_level=signal_level,
        confidence=round(kc, 4),
        knowledge_confidence=round(knowledge_conf, 4),
        market_score=analysis.score,
        supporting_mechanisms=analysis.supporting_mechanisms,
        counter_mechanisms=analysis.counter_mechanisms,
        active_chains=analysis.active_chains,
        active_scripts=analysis.active_scripts,
        expected_direction=analysis.direction,
        environment=analysis.environment,
        risk_level=risk_level,
        headline=headline,
        explanation=explanation,
        key_risk=key_risk,
        display_tier=display_tier,
        data_quality="seed",
        generated_at=generated_at,
    )


def run() -> dict:
    _ARTIFACTS.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()

    from oracle.market_intelligence.schema import MarketIntelligenceSummary

    log.info("Market Intelligence Pipeline starting…")

    # ── Load inputs ───────────────────────────────────────────────────────────
    activations_raw:  list = _load_json(_ARTIFACTS / "knowledge_activations.json",    [])  # type: ignore
    effective_weights: dict = _load_json(_ARTIFACTS / "knowledge_effective_weights.json", {})  # type: ignore
    learning_summary:  dict = _load_json(_ARTIFACTS / "knowledge_learning_summary.json", {})  # type: ignore
    seed_profiles:     dict = {}  # Stage 1: no external profiles needed

    # Try loading team profiles from seed if available
    try:
        from oracle.knowledge.seed import list_seeded_teams, get_team_profile
        for tid in list_seeded_teams():
            p = get_team_profile(tid)
            seed_profiles[tid] = p.to_dict()
    except Exception as exc:
        log.debug("Could not load seed profiles: %s", exc)

    trend_map: dict[str, str] = learning_summary.get("trend_map", {})
    activations_by_match: dict[str, dict] = {
        a["match_id"]: a for a in activations_raw if "match_id" in a
    }

    if not activations_by_match:
        log.info("No knowledge activations found — writing empty artifacts")
        _write("market_intelligence_cards.json", [])
        summary = MarketIntelligenceSummary(
            generated_at=generated_at, stage="stage_1",
            n_matches=0, n_cards=0,
            n_strong_signals=0, n_moderate_signals=0,
            n_watchlist=0, n_no_signal=0,
            top_corners_signals=[], top_cards_signals=[], top_shots_signals=[],
            dominant_mechanisms=[], notes=["No knowledge activations available."],
        )
        _write("market_intelligence_summary.json", summary.to_dict())
        return {"n_matches": 0, "n_cards": 0}

    # ── Build cards ───────────────────────────────────────────────────────────
    all_cards = []
    for match_id, activation in activations_by_match.items():
        home_team = activation.get("home_team", match_id.split("_vs_")[0] if "_vs_" in match_id else "home")
        away_team = activation.get("away_team", match_id.split("_vs_")[-1] if "_vs_" in match_id else "away")
        home_profile = seed_profiles.get(home_team)
        away_profile = seed_profiles.get(away_team)

        for mtype in ("corners", "cards", "shots"):
            try:
                card = _build_card(
                    match_id=match_id,
                    market_type=mtype,
                    activation=activation,
                    home_team=home_team,
                    away_team=away_team,
                    home_profile=home_profile,
                    away_profile=away_profile,
                    effective_weights=effective_weights,
                    trend_map=trend_map,
                    generated_at=generated_at,
                )
                all_cards.append(card)
            except Exception as exc:
                log.warning("Card build failed for %s/%s: %s", match_id, mtype, exc)

    log.info("Generated %d market intelligence cards for %d matches", len(all_cards), len(activations_by_match))

    # ── Build summary ─────────────────────────────────────────────────────────
    n_strong   = sum(1 for c in all_cards if c.signal_level == "strong_signal")
    n_moderate = sum(1 for c in all_cards if c.signal_level == "moderate_signal")
    n_watchlist = sum(1 for c in all_cards if c.signal_level == "watchlist")
    n_no_signal = sum(1 for c in all_cards if c.signal_level == "no_signal")

    def _top_signals(mtype: str) -> list[dict]:
        mtype_cards = [c for c in all_cards if c.market_type == mtype
                       and c.signal_level in ("strong_signal", "moderate_signal")]
        mtype_cards.sort(key=lambda c: c.market_score, reverse=True)
        return [{"match_id": c.match_id, "signal": c.signal_level,
                 "score": c.market_score, "direction": c.expected_direction} for c in mtype_cards[:5]]

    # Collect dominant mechanisms
    all_mechs: list[str] = []
    for c in all_cards:
        all_mechs.extend(c.supporting_mechanisms)
    from collections import Counter
    dominant = [m for m, _ in Counter(all_mechs).most_common(5)]

    notes: list[str] = [
        f"Generated {len(all_cards)} cards across {len(activations_by_match)} matches.",
        f"Strong signals: {n_strong} | Moderate: {n_moderate} | Watchlist: {n_watchlist}.",
    ]
    if not trend_map:
        notes.append("No live learning trends yet — weights at calibration baseline.")

    summary = MarketIntelligenceSummary(
        generated_at=generated_at,
        stage="stage_1",
        n_matches=len(activations_by_match),
        n_cards=len(all_cards),
        n_strong_signals=n_strong,
        n_moderate_signals=n_moderate,
        n_watchlist=n_watchlist,
        n_no_signal=n_no_signal,
        top_corners_signals=_top_signals("corners"),
        top_cards_signals=_top_signals("cards"),
        top_shots_signals=_top_signals("shots"),
        dominant_mechanisms=dominant,
        notes=notes,
    )

    # ── Write artifacts ───────────────────────────────────────────────────────
    _write("market_intelligence_cards.json", [c.to_dict() for c in all_cards])
    _write("market_intelligence_summary.json", summary.to_dict())

    # Optional parquet
    try:
        import polars as pl
        df = pl.DataFrame([c.to_dict() for c in all_cards])
        df.write_parquet(_ARTIFACTS / "market_intelligence.parquet")
        log.info("  wrote market_intelligence.parquet (%d rows)", len(df))
    except Exception as exc:
        log.debug("Parquet write skipped: %s", exc)

    result = {
        "n_matches":    len(activations_by_match),
        "n_cards":      len(all_cards),
        "n_strong":     n_strong,
        "n_moderate":   n_moderate,
        "n_watchlist":  n_watchlist,
    }
    log.info(
        "Market Intelligence complete — %d matches | %d cards | %d strong | %d moderate",
        result["n_matches"], result["n_cards"], result["n_strong"], result["n_moderate"],
    )
    return result


def _write(filename: str, data: object) -> None:
    path = _ARTIFACTS / filename
    path.write_text(json.dumps(data, indent=2, default=str))
    log.info("  wrote %s (%d bytes)", filename, path.stat().st_size)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run()
