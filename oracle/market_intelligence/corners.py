"""
Corners Intelligence Engine — Week 28.

Builds expected corner environment from football mechanisms:
  Possession Control vs Low Block  →  elevated corners (C-03)
  Wing Overload / Direct Play      →  elevated corners (wide crossing)
  Set Piece Reliance               →  more set piece opportunities
  Low Block Deflections            →  deflected shots → corners (C-05)
  Counter Attack dynamic           →  suppressed corners (attacks finish before crossing phase)

Score: 0–100 (baseline 50).
Environment: very_low | low | normal | high | very_high
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ── Corner environment scoring ────────────────────────────────────────────────

# Chain modifiers (positive = more corners)
_CHAIN_SCORES: dict[str, float] = {
    "C-03": +18.0,   # possession → corner pressure (strongest mechanism)
    "C-05": +14.0,   # low block deflections → corners
    "S-07": +10.0,   # set piece overload chain
    "B-05": +6.0,    # pressing trap → transitions → fewer corners (but some counter corners)
    "G-07": +8.0,    # low block stalemate → defending team forces corners
    "G-01": -6.0,    # counter vs high line → attacks finish with shots, fewer corners
    "K-02": +0.0,    # knockout pressure (neutral on corners)
}

# Script modifiers
_SCRIPT_SCORES: dict[str, float] = {
    "defensive_siege":       +12.0,  # compact defense → repeated corner attempts
    "tactical_neutralization": +6.0,  # frustrated attacks → corners as fallback
    "set_piece_war":         +14.0,  # match dominated by set pieces → elevated corners
    "high_press_feast":      -6.0,   # attacks via through balls/press → fewer corners
    "counter_attack_trap":   -10.0,  # attacks finish with shots before crossing phase
    "favorite_dominance":    +4.0,   # dominant team generates sustained corner pressure
    "cagey_knockout":        +8.0,   # defensive caution → corners as main attacking outlet
    "early_goal_chaos":      -4.0,   # open game → fewer structured corner sequences
    "late_equalizer_pressure": +6.0, # chasing team lumps it → corners
}

# Archetype matchup modifiers (home_arch vs away_arch → score delta)
_ARCHETYPE_MATCHUPS: dict[tuple[str, str], float] = {
    ("possession_control", "counter_attack"):       +16.0,
    ("possession_control", "low_block"):            +20.0,
    ("possession_control", "tournament_survival"):  +14.0,
    ("possession_control", "defensive_siege"):      +18.0,   # won't exist as archetype but guard
    ("direct_play", "counter_attack"):              +10.0,
    ("direct_play", "low_block"):                   +12.0,
    ("direct_play", "possession_control"):          +8.0,
    ("high_press", "counter_attack"):               +6.0,
    ("high_press", "low_block"):                    +10.0,
    ("set_piece_heavy", "any"):                     +12.0,   # special-cased below
    ("counter_attack", "counter_attack"):           -18.0,
    ("counter_attack", "possession_control"):       -8.0,
}

# Profile trait modifiers (applied to each team separately, halved)
_PROFILE_TRAITS: dict[str, float] = {
    "set_piece_reliance_high":    +8.0,
    "set_piece_reliance_medium":  +3.0,
    "aerial_reliance_high":       +6.0,    # aerial balls → more corners when contested
    "defensive_block_low_block":  +7.0,    # low block defense → more corner-inducing attacks
    "tempo_high":                 +3.0,    # high tempo → more corner sequences
    "pressing_intensity_low":     +4.0,    # low press → opponent can deliver crosses
}


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _profile_bonus(profile: Optional[dict]) -> tuple[float, list[str]]:
    """Extract corner-relevant traits from a team profile dict."""
    if not profile:
        return 0.0, []
    bonus = 0.0
    mechanisms: list[str] = []

    spr = profile.get("set_piece_reliance", "medium")
    if spr == "high":
        bonus += _PROFILE_TRAITS["set_piece_reliance_high"]
        mechanisms.append("set piece reliance (high)")
    elif spr == "medium":
        bonus += _PROFILE_TRAITS["set_piece_reliance_medium"]

    ar = profile.get("aerial_reliance", "medium")
    if ar == "high":
        bonus += _PROFILE_TRAITS["aerial_reliance_high"]
        mechanisms.append("aerial reliance (high)")

    db = profile.get("defensive_block", "mid_block")
    if db == "low_block":
        bonus += _PROFILE_TRAITS["defensive_block_low_block"]
        mechanisms.append("low defensive block")

    tp = profile.get("tempo", "medium")
    if tp == "high":
        bonus += _PROFILE_TRAITS["tempo_high"]

    pi = profile.get("pressing_intensity", "medium")
    if pi == "low":
        bonus += _PROFILE_TRAITS["pressing_intensity_low"]

    return bonus, mechanisms


def _score_to_environment(score: float) -> str:
    if score >= 75:
        return "very_high"
    if score >= 62:
        return "high"
    if score >= 42:
        return "normal"
    if score >= 28:
        return "low"
    return "very_low"


@dataclass
class CornersAnalysis:
    score:               float
    environment:         str
    supporting_mechanisms: list[str]
    counter_mechanisms:    list[str]
    active_chains:         list[str]
    active_scripts:        list[str]
    direction:             str        # "elevated" | "neutral" | "suppressed"


def analyze_corners(
    activation: Optional[dict],
    home_profile: Optional[dict] = None,
    away_profile: Optional[dict] = None,
    effective_weights: Optional[dict] = None,
) -> CornersAnalysis:
    """
    Compute expected corner environment from football mechanisms.

    Parameters
    ----------
    activation:         knowledge_activation dict for this match
    home_profile:       TeamIdentityProfile.to_dict() for home team (optional)
    away_profile:       TeamIdentityProfile.to_dict() for away team (optional)
    effective_weights:  knowledge_effective_weights dict (chains/scripts buckets)
    """
    activation = activation or {}
    weights = effective_weights or {}
    chain_weights: dict[str, float] = weights.get("chains", {})
    script_weights: dict[str, float] = weights.get("scripts", {})

    score = 50.0  # baseline
    supporting: list[str] = []
    counter:    list[str] = []
    used_chains:  list[str] = []
    used_scripts: list[str] = []

    # ── 1. Activated chains ───────────────────────────────────────────────────
    for chain in activation.get("activated_chains", []):
        cid   = chain.get("chain_id", "")
        cconf = float(chain.get("confidence", 0.5))
        delta = _CHAIN_SCORES.get(cid, 0.0)
        if delta == 0.0:
            continue
        w = float(chain_weights.get(cid, 1.0))
        adjusted = delta * cconf * w
        score += adjusted
        if delta > 0:
            used_chains.append(cid)
            if cid == "C-03":
                supporting.append("Possession→Corner pressure (C-03)")
            elif cid == "C-05":
                supporting.append("Low Block Deflections→Corners (C-05)")
            elif cid == "S-07":
                supporting.append("Set Piece Overload (S-07)")
            elif cid == "G-07":
                supporting.append("Low Block Stalemate (G-07)")
        elif delta < 0:
            counter.append(f"Counter chain {cid} reduces crossing phase")

    # ── 2. Activated scripts ──────────────────────────────────────────────────
    for script in activation.get("activated_scripts", []):
        sid   = script.get("script_id", "")
        prob  = float(script.get("probability", 0.5))
        delta = _SCRIPT_SCORES.get(sid, 0.0)
        if delta == 0.0:
            continue
        w = float(script_weights.get(sid, 1.0))
        adjusted = delta * prob * w
        score += adjusted
        if delta > 0:
            used_scripts.append(sid)
            supporting.append(f"{sid.replace('_',' ').title()} script")
        else:
            counter.append(f"{sid.replace('_',' ').title()} script suppresses corners")

    # ── 3. Archetype matchup ──────────────────────────────────────────────────
    home_arch = activation.get("home_archetype", "unknown")
    away_arch = activation.get("away_archetype", "unknown")
    matchup_delta = _ARCHETYPE_MATCHUPS.get((home_arch, away_arch), 0.0)
    if matchup_delta == 0.0:
        # Also check reverse
        matchup_delta = _ARCHETYPE_MATCHUPS.get((away_arch, home_arch), 0.0) * 0.7

    # Special-case set_piece_heavy — applies regardless of opponent
    if home_arch == "set_piece_heavy" or away_arch == "set_piece_heavy":
        score += _ARCHETYPE_MATCHUPS.get(("set_piece_heavy", "any"), 12.0)
        supporting.append("Set Piece Heavy archetype elevates corner volume")

    if matchup_delta > 2.0:
        score += matchup_delta
        supporting.append(
            f"Archetype matchup ({home_arch} vs {away_arch}) favors corner volume"
        )
    elif matchup_delta < -2.0:
        score += matchup_delta
        counter.append(
            f"Archetype matchup ({home_arch} vs {away_arch}) reduces corner volume"
        )

    # ── 4. Team profile traits ────────────────────────────────────────────────
    home_bonus, home_mechs = _profile_bonus(home_profile)
    away_bonus, away_mechs = _profile_bonus(away_profile)
    score += (home_bonus + away_bonus) * 0.5
    for m in set(home_mechs + away_mechs):
        supporting.append(m)

    # ── 5. Clamp and classify ─────────────────────────────────────────────────
    score = _clamp(score)
    environment = _score_to_environment(score)
    direction   = "elevated" if score >= 58 else ("suppressed" if score <= 42 else "neutral")

    return CornersAnalysis(
        score=round(score, 2),
        environment=environment,
        supporting_mechanisms=supporting[:6],
        counter_mechanisms=counter[:4],
        active_chains=used_chains,
        active_scripts=used_scripts,
        direction=direction,
    )
