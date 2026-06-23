"""
Cards Intelligence Engine — Week 28.

Builds expected disciplinary environment from football mechanisms:
  High Press vs Counter Attack  →  tactical fouls (T-01 / B-05)
  Late Knockout Pressure        →  desperation fouls → cards
  Tournament Survival           →  defensive fouls to protect result
  Controlled Possession         →  fewer cards (game managed)
  Press Failure Tactical Foul   →  pressing team caught on counter → fouls

Score: 0–100 (baseline 50).
Environment: very_low | low | normal | high | very_high
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ── Card environment scoring ──────────────────────────────────────────────────

_CHAIN_SCORES: dict[str, float] = {
    "B-05": +14.0,   # pressing trap → tactical fouls when beaten on counter
    "G-01": +10.0,   # counter attack vs high line → fouls to stop breaks
    "K-02": +12.0,   # knockout pressure → desperate defending → cards
    "G-07": -6.0,    # low block stalemate → controlled game, fewer flashpoints
    "C-03": -4.0,    # possession control → fewer fouls needed
    "S-03": +8.0,    # if S-03 is a set piece chain → card from fouls near box
    "S-07": +6.0,    # set piece contest → body contact → cards
    "T-01": +16.0,   # tactical foul chain: the most direct cards signal
}

_SCRIPT_SCORES: dict[str, float] = {
    "high_press_feast":       +14.0,  # two pressing teams → fouls when press beaten
    "counter_attack_trap":    +10.0,  # counter threat → defensive fouls
    "late_equalizer_pressure": +12.0, # desperate pressing → cards
    "set_piece_war":          +8.0,   # set pieces → cynical fouls near box
    "cagey_knockout":         +10.0,  # tournament nerves → preventive fouls
    "defensive_siege":        +8.0,   # deep defending team under pressure → fouls
    "tactical_neutralization": +6.0,  # frustrated teams → increased foul rate
    "favorite_dominance":     -8.0,   # dominant possession → fewer fouls needed
    "early_goal_chaos":       +6.0,   # high energy → collisions → cards
}

_ARCHETYPE_MATCHUPS: dict[tuple[str, str], float] = {
    ("high_press",         "counter_attack"):       +16.0,
    ("high_press",         "possession_control"):   +8.0,
    ("high_press",         "high_press"):           +12.0,
    ("counter_attack",     "high_press"):           +14.0,
    ("counter_attack",     "possession_control"):   +6.0,
    ("tournament_survival","high_press"):           +14.0,
    ("tournament_survival","possession_control"):   +10.0,
    ("low_block",          "high_press"):           +12.0,
    ("low_block",          "direct_play"):          +10.0,
    ("possession_control", "possession_control"):   -10.0,
    ("possession_control", "counter_attack"):       -4.0,
}

_PROFILE_TRAITS: dict[str, float] = {
    "pressing_intensity_high":  +8.0,   # high press → more tactical fouls
    "pressing_intensity_low":   -4.0,   # low press → fewer fouls
    "defensive_block_low_block": +6.0,  # deep defense → more fouls
    "tempo_high":               +5.0,   # high tempo → more physical play
    "tempo_slow":               -5.0,   # slow tempo → more controlled
    "risk_profile_high":        +6.0,   # risk-taking team → more cards
    "risk_profile_low":         -4.0,   # conservative → fewer cards
}


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _profile_bonus(profile: Optional[dict]) -> tuple[float, list[str]]:
    if not profile:
        return 0.0, []
    bonus = 0.0
    mechanisms: list[str] = []

    pi = profile.get("pressing_intensity", "medium")
    if pi == "high":
        bonus += _PROFILE_TRAITS["pressing_intensity_high"]
        mechanisms.append("high pressing intensity (tactical fouls risk)")
    elif pi == "low":
        bonus += _PROFILE_TRAITS["pressing_intensity_low"]

    db = profile.get("defensive_block", "mid_block")
    if db == "low_block":
        bonus += _PROFILE_TRAITS["defensive_block_low_block"]
        mechanisms.append("low defensive block (fouls under pressure)")

    tp = profile.get("tempo", "medium")
    if tp == "high":
        bonus += _PROFILE_TRAITS["tempo_high"]
    elif tp == "slow":
        bonus += _PROFILE_TRAITS["tempo_slow"]

    rp = profile.get("risk_profile", "medium")
    if rp == "high":
        bonus += _PROFILE_TRAITS["risk_profile_high"]
        mechanisms.append("high risk profile")
    elif rp == "low":
        bonus += _PROFILE_TRAITS["risk_profile_low"]

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
class CardsAnalysis:
    score:               float
    environment:         str
    supporting_mechanisms: list[str]
    counter_mechanisms:    list[str]
    active_chains:         list[str]
    active_scripts:        list[str]
    direction:             str


def analyze_cards(
    activation: Optional[dict],
    home_profile: Optional[dict] = None,
    away_profile: Optional[dict] = None,
    effective_weights: Optional[dict] = None,
) -> CardsAnalysis:
    """
    Compute expected disciplinary environment from football mechanisms.
    """
    activation = activation or {}
    weights = effective_weights or {}
    chain_weights: dict[str, float] = weights.get("chains", {})
    script_weights: dict[str, float] = weights.get("scripts", {})

    score = 50.0
    supporting: list[str] = []
    counter:    list[str] = []
    used_chains:  list[str] = []
    used_scripts: list[str] = []

    # ── 1. Chains ─────────────────────────────────────────────────────────────
    for chain in activation.get("activated_chains", []):
        cid   = chain.get("chain_id", "")
        cconf = float(chain.get("confidence", 0.5))
        delta = _CHAIN_SCORES.get(cid, 0.0)
        if delta == 0.0:
            continue
        w = float(chain_weights.get(cid, 1.0))
        score += delta * cconf * w
        if delta > 0:
            used_chains.append(cid)
            if cid == "T-01":
                supporting.append("Tactical Foul Chain (T-01) — direct cards mechanism")
            elif cid == "B-05":
                supporting.append("Press Failure Tactical Foul (B-05)")
            elif cid == "G-01":
                supporting.append("Counter Attack Break Foul (G-01)")
            elif cid == "K-02":
                supporting.append("Knockout Pressure Desperation (K-02)")
        else:
            counter.append(f"Chain {cid} suppresses card risk")

    # ── 2. Scripts ────────────────────────────────────────────────────────────
    for script in activation.get("activated_scripts", []):
        sid  = script.get("script_id", "")
        prob = float(script.get("probability", 0.5))
        delta = _SCRIPT_SCORES.get(sid, 0.0)
        if delta == 0.0:
            continue
        w = float(script_weights.get(sid, 1.0))
        score += delta * prob * w
        if delta > 0:
            used_scripts.append(sid)
            supporting.append(f"{sid.replace('_',' ').title()} → elevated cards")
        else:
            counter.append(f"{sid.replace('_',' ').title()} → controlled environment")

    # ── 3. Archetype matchup ──────────────────────────────────────────────────
    home_arch = activation.get("home_archetype", "unknown")
    away_arch = activation.get("away_archetype", "unknown")
    matchup_delta = _ARCHETYPE_MATCHUPS.get((home_arch, away_arch), 0.0)
    if matchup_delta == 0.0:
        matchup_delta = _ARCHETYPE_MATCHUPS.get((away_arch, home_arch), 0.0) * 0.7

    if matchup_delta > 2.0:
        score += matchup_delta
        supporting.append(
            f"Archetype matchup ({home_arch} vs {away_arch}) drives card risk"
        )
    elif matchup_delta < -2.0:
        score += matchup_delta
        counter.append(
            f"Archetype matchup ({home_arch} vs {away_arch}) reduces card risk"
        )

    # ── 4. Profile traits ─────────────────────────────────────────────────────
    home_bonus, home_mechs = _profile_bonus(home_profile)
    away_bonus, away_mechs = _profile_bonus(away_profile)
    score += (home_bonus + away_bonus) * 0.5
    for m in set(home_mechs + away_mechs):
        supporting.append(m)

    score = _clamp(score)
    environment = _score_to_environment(score)
    direction   = "elevated" if score >= 58 else ("suppressed" if score <= 42 else "neutral")

    return CardsAnalysis(
        score=round(score, 2),
        environment=environment,
        supporting_mechanisms=supporting[:6],
        counter_mechanisms=counter[:4],
        active_chains=used_chains,
        active_scripts=used_scripts,
        direction=direction,
    )
