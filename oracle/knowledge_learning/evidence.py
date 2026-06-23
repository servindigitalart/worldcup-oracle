"""
Evidence logging — Week 27.

Builds EvidenceEntry records from:
  1. Completed matches in live_results.json (WC 2026)
  2. knowledge_activations.json (current activations)
  3. betting_theses.json (top thesis per match)

Evidence is append-only. Never mutate existing entries.
Entry IDs are deterministic: sha1(match_id + data_source).
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from oracle.knowledge_learning.schema import EvidenceEntry

log = logging.getLogger(__name__)

_ARTIFACTS = Path("data/artifacts")


def _entry_id(match_id: str, source: str) -> str:
    key = f"{match_id}:{source}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def _load_json(path: Path, fallback: object = None) -> object:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return fallback if fallback is not None else []
    except Exception as exc:
        log.warning("Could not load %s: %s", path.name, exc)
        return fallback if fallback is not None else []


def _top_thesis_for_match(theses: list[dict], match_id: str) -> Optional[dict]:
    match_theses = [t for t in theses if t.get("match_id") == match_id]
    if not match_theses:
        return None
    return max(match_theses, key=lambda t: t.get("opportunity_score", 0))


def build_evidence_log(artifacts_path: Optional[Path] = None) -> list[EvidenceEntry]:
    """
    Build evidence entries from completed WC 2026 matches.

    Matches live_results with knowledge_activations to create structured
    evidence records. Returns empty list if no results available.
    """
    arts = artifacts_path or _ARTIFACTS
    recorded_at = datetime.now(timezone.utc).isoformat()

    live_results    = _load_json(arts / "live_results.json", [])
    activations_raw = _load_json(arts / "knowledge_activations.json", [])
    theses_raw      = _load_json(arts / "betting_theses.json", [])

    if not live_results:
        log.info("No live results available — evidence log will be empty")
        return []

    # Index activations by match_id
    activations: dict[str, dict] = {}
    for a in activations_raw:
        mid = a.get("match_id", "")
        if mid:
            activations[mid] = a

    theses: list[dict] = theses_raw if isinstance(theses_raw, list) else []

    entries: list[EvidenceEntry] = []
    finished = [r for r in live_results if r.get("status") == "finished"]

    for result in finished:
        match_id = result.get("match_id", "")
        if not match_id:
            continue

        activation = activations.get(match_id, {})
        top_thesis  = _top_thesis_for_match(theses, match_id)

        chains   = [c["chain_id"]  for c in activation.get("activated_chains", [])]
        scripts  = [s["script_id"] for s in activation.get("activated_scripts", [])]
        managers = [
            f"{p['manager_id']}:{p['pattern_id']}"
            for p in activation.get("activated_manager_patterns", [])
            if p.get("manager_id") and p.get("pattern_id")
        ]
        archetypes = [
            activation.get("home_archetype", ""),
            activation.get("away_archetype", ""),
        ]
        archetypes = [a for a in archetypes if a and a != "unknown"]

        entries.append(EvidenceEntry(
            entry_id=_entry_id(match_id, "live_2026"),
            match_id=match_id,
            date=result.get("date", result.get("kickoff_at", ""))[:10],
            home_team=result.get("home_team", ""),
            away_team=result.get("away_team", ""),
            activated_chain_ids=chains,
            activated_script_ids=scripts,
            activated_manager_patterns=managers,
            activated_archetype_ids=archetypes,
            knowledge_confidence=float(activation.get("knowledge_confidence", 0.30)),
            top_thesis_market=top_thesis.get("market_type", "") if top_thesis else "",
            top_opportunity_score=int(top_thesis.get("opportunity_score", 0)) if top_thesis else 0,
            data_source="live_2026",
            recorded_at=recorded_at,
        ))

    log.info("Built %d evidence entries from live results", len(entries))
    return entries
