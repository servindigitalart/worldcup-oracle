"""
Knowledge Engine pipeline — Week 25E.

Reads:    data/artifacts/match_betting_cards.json  (match list)
Writes:   data/artifacts/knowledge_activations.json
          data/artifacts/causal_chain_activations.json
          data/artifacts/game_script_activations.json
          data/artifacts/knowledge_summary.json

Exports:  frontend/src/data/knowledge_activations.json
          frontend/src/data/causal_chain_activations.json
          frontend/src/data/game_script_activations.json
          frontend/src/data/knowledge_summary.json

Usage:
    python -m oracle.pipeline.knowledge
    make knowledge
"""
from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from oracle.knowledge.explain import build_knowledge_explanation
from oracle.knowledge.resolver import resolve_knowledge_for_match
from oracle.knowledge.schema import KnowledgeActivation
from oracle.knowledge.seed import list_seeded_teams

log = logging.getLogger(__name__)

_ARTIFACTS = Path("data/artifacts")
_FRONTEND  = Path("frontend/src/data")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_match_list() -> list[dict]:
    path = _ARTIFACTS / "match_betting_cards.json"
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        log.warning("match_betting_cards.json not found — returning empty list")
        return []
    except Exception as exc:
        log.error("Failed to load match_betting_cards.json: %s", exc)
        return []


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))
    kb = path.stat().st_size / 1024
    log.info("  wrote %s  (%.1f KB)", path, kb)


# ── Summary builder ────────────────────────────────────────────────────────────

def _build_summary(
    activations: list[KnowledgeActivation],
    generated_at: str,
) -> dict:
    seeded = set(list_seeded_teams())
    n_full    = sum(
        1 for a in activations
        if a.home_team in seeded and a.away_team in seeded
    )
    n_partial = sum(
        1 for a in activations
        if (a.home_team in seeded) != (a.away_team in seeded)
    )
    n_unknown = len(activations) - n_full - n_partial

    chain_counter: Counter = Counter()
    script_counter: Counter = Counter()
    for act in activations:
        for c in act.activated_chains:
            chain_counter[c.chain_id] += 1
        for s in act.activated_scripts[:1]:  # top script only
            script_counter[s.script_id] += 1

    avg_conf = (
        round(sum(a.knowledge_confidence for a in activations) / len(activations), 3)
        if activations else 0.0
    )

    return {
        "generated_at":          generated_at,
        "n_matches":             len(activations),
        "n_with_full_profiles":  n_full,
        "n_with_partial_profiles": n_partial,
        "n_unknown_profiles":    n_unknown,
        "n_chain_activations":   sum(len(a.activated_chains) for a in activations),
        "n_script_activations":  sum(len(a.activated_scripts) for a in activations),
        "avg_knowledge_confidence": avg_conf,
        "most_common_scripts":   script_counter.most_common(5),
        "most_common_chains":    chain_counter.most_common(5),
        "stage":                 "stage_1",
    }


# ── Main pipeline ──────────────────────────────────────────────────────────────

def run() -> dict:
    """Generate knowledge activations for all matches and write artifacts."""
    log.info("Knowledge Engine pipeline starting…")

    matches = _load_match_list()
    if not matches:
        log.warning("No matches found — writing empty artifacts")
        empty_summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "n_matches": 0, "n_with_full_profiles": 0,
            "n_with_partial_profiles": 0, "n_unknown_profiles": 0,
            "n_chain_activations": 0, "n_script_activations": 0,
            "avg_knowledge_confidence": 0.0,
            "most_common_scripts": [], "most_common_chains": [],
            "stage": "stage_1",
        }
        for path in [
            _ARTIFACTS / "knowledge_activations.json",
            _ARTIFACTS / "causal_chain_activations.json",
            _ARTIFACTS / "game_script_activations.json",
            _FRONTEND  / "knowledge_activations.json",
            _FRONTEND  / "causal_chain_activations.json",
            _FRONTEND  / "game_script_activations.json",
        ]:
            _write_json(path, [])
        _write_json(_ARTIFACTS / "knowledge_summary.json", empty_summary)
        _write_json(_FRONTEND  / "knowledge_summary.json", empty_summary)
        return empty_summary

    generated_at = datetime.now(timezone.utc).isoformat()
    activations: list[KnowledgeActivation] = []

    for card in matches:
        match_id  = card["match_id"]
        home_team = card.get("home_team", "")
        away_team = card.get("away_team", "")
        try:
            act = resolve_knowledge_for_match(
                match_id=match_id,
                home_team=home_team,
                away_team=away_team,
                generated_at=generated_at,
            )
            activations.append(act)
        except Exception as exc:
            log.error("Failed knowledge resolution for %s: %s", match_id, exc)

    log.info("Resolved knowledge for %d matches", len(activations))

    # ── Serialise to dicts ─────────────────────────────────────────────────────
    activation_dicts = [a.to_dict() for a in activations]

    # Flat chain activations (all chains, all matches)
    chain_rows: list[dict] = []
    for a in activations:
        for c in a.activated_chains:
            chain_rows.append({
                "match_id":    a.match_id,
                "home_team":   a.home_team,
                "away_team":   a.away_team,
                **c.to_dict(),
            })

    # Flat script activations (top 3 per match)
    script_rows: list[dict] = []
    for a in activations:
        for s in a.activated_scripts[:3]:
            script_rows.append({
                "match_id":  a.match_id,
                "home_team": a.home_team,
                "away_team": a.away_team,
                **s.to_dict(),
            })

    summary = _build_summary(activations, generated_at)

    # Attach per-match explanations to the activations export
    for i, act in enumerate(activations):
        headline, body, key_risk = build_knowledge_explanation(act)
        activation_dicts[i]["knowledge_headline"] = headline
        activation_dicts[i]["knowledge_body"]     = body
        activation_dicts[i]["knowledge_key_risk"] = key_risk

    # ── Write artifacts ────────────────────────────────────────────────────────
    _write_json(_ARTIFACTS / "knowledge_activations.json",     activation_dicts)
    _write_json(_ARTIFACTS / "causal_chain_activations.json",  chain_rows)
    _write_json(_ARTIFACTS / "game_script_activations.json",   script_rows)
    _write_json(_ARTIFACTS / "knowledge_summary.json",         summary)

    # ── Export to frontend ─────────────────────────────────────────────────────
    _write_json(_FRONTEND / "knowledge_activations.json",     activation_dicts)
    _write_json(_FRONTEND / "causal_chain_activations.json",  chain_rows)
    _write_json(_FRONTEND / "game_script_activations.json",   script_rows)
    _write_json(_FRONTEND / "knowledge_summary.json",         summary)

    log.info(
        "Knowledge pipeline complete: %d matches, %d chains, %d scripts",
        summary["n_matches"],
        summary["n_chain_activations"],
        summary["n_script_activations"],
    )
    return summary


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-8s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    result = run()
    print(json.dumps(
        {k: v for k, v in result.items()},
        indent=2,
    ))
