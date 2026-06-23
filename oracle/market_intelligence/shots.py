"""
Shots Intelligence Engine — Week 28.

Builds expected shot environment from football mechanisms:
  Favorite Dominance     →  sustained territorial pressure → high shots
  High Press Feast       →  both teams pressing → both creating chances
  Possession Control     →  sustained attacking phases → elevated shots
  Counter Attack Trap    →  transitions → fewer shots overall (quick strikes)
  Tactical Neutralization→  compact shape → suppressed shot volume
  Open Shootout          →  both teams exposed → very high shots

Score: 0–100 (baseline 50).
Tracks: shot_direction (elevated/neutral/suppressed) + environment tier.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ── Shot environment scoring ──────────────────────────────────────────────────

_CHAIN_SCORES: dict[str, float] = {
    "G-01": +12.0,   # counter vs high line → fast breaks create shots on both ends
    "C-03": +6.0,    # possession → shots via sustained pressure
    "G-07": -12.0,   # low block stalemate → shots blocked/off target, low volume
    "B-05": +8.0,    # press trap → transition chances → shots
    "K-02": +6.0,    # knockout pressure → more aggressive attacking → shots
    "S-03": +4.0,    # set piece → shots from delivery zones
}

_SCRIPT_SCORES: dict[str, float] = {
    "favorite_dominance":      +16.0,  # dominant team generates sustained xG
    "high_press_feast":        +14.0,  # both teams press → both creating
    "counter_attack_trap":     +8.0,   # counters end in shots quickly
    "early_goal_chaos":        +12.0,  # high-energy open game → shots
    "tactical_neutralization": -14.0,  # both compact → suppressed shots
    "defensive_siege":         -10.0,  # one team locked down → fewer shots
    "cagey_knockout":          -8.0,   # cautious → limited shot creation
    "set_piece_war":           +4.0,   # set pieces create some shot opportunities
    "late_equalizer_pressure": +8.0,   # desperate pressing → more shots
}

_ARCHETYPE_MATCHUPS: dict[tuple[str, str], float] = {
    ("possession_control", "counter_attack"):       +10.0,
    ("possession_control", "high_press"):           +8.0,
    ("high_press",         "high_press"):           +18.0,
    ("high_press",         "counter_attack"):       +12.0,
    ("high_press",         "possession_control"):   +10.0,
    ("direct_play",        "possession_control"):   +8.0,
    ("direct_play",        "high_press"):           +12.0,
    ("possession_control", "possession_control"):   +6.0,
    ("counter_attack",     "counter_attack"):       -8.0,   # both transition → fewer shots
    ("low_block",          "possession_control"):   -6.0,
    ("tournament_survival","counter_attack"):       -10.0,
    ("tournament_survival","possession_control"):   -6.0,
}

_PROFILE_TRAITS: dict[str, float] = {
    "pressing_intensity_high": +8.0,   # high press → forced turnovers → shots
    "tempo_high":              +6.0,   # high tempo → more attacking intent
    "tempo_slow":              -6.0,   # slow tempo → more controlled
    "risk_profile_high":       +8.0,   # attacking risk-taking → shots
    "risk_profile_low":        -6.0,   # conservative → fewer shots
    "defensive_block_high_line": +4.0, # high line → space in behind → shots
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
        mechanisms.append("high pressing intensity (forced turnovers → chances)")

    tp = profile.get("tempo", "medium")
    if tp == "high":
        bonus += _PROFILE_TRAITS["tempo_high"]
        mechanisms.append("high tempo (attacking intent)")
    elif tp == "slow":
        bonus += _PROFILE_TRAITS["tempo_slow"]

    rp = profile.get("risk_profile", "medium")
    if rp == "high":
        bonus += _PROFILE_TRAITS["risk_profile_high"]
        mechanisms.append("high risk profile (attacking ambition)")
    elif rp == "low":
        bonus += _PROFILE_TRAITS["risk_profile_low"]

    db = profile.get("defensive_block", "mid_block")
    if db == "high_line":
        bonus += _PROFILE_TRAITS["defensive_block_high_line"]

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
class ShotsAnalysis:
    score:               float
    environment:         str
    supporting_mechanisms: list[str]
    counter_mechanisms:    list[str]
    active_chains:         list[str]
    active_scripts:        list[str]
    direction:             str


def analyze_shots(
    activation: Optional[dict],
    home_profile: Optional[dict] = None,
    away_profile: Optional[dict] = None,
    effective_weights: Optional[dict] = None,
) -> ShotsAnalysis:
    """
    Compute expected shot environment from football mechanisms.
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
            if cid == "G-01":
                supporting.append("Counter vs High Line (G-01) — shots on both ends")
            elif cid == "C-03":
                supporting.append("Possession Pressure (C-03) — sustained attack")
            elif cid == "B-05":
                supporting.append("Press Trap (B-05) — transition shots")
            elif cid == "K-02":
                supporting.append("Knockout Urgency (K-02) — increased attacking")
        else:
            counter.append(f"Chain {cid} suppresses shot volume")

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
            supporting.append(f"{sid.replace('_',' ').title()} → elevated shots")
        else:
            counter.append(f"{sid.replace('_',' ').title()} → suppressed shots")

    # ── 3. Archetype matchup ──────────────────────────────────────────────────
    home_arch = activation.get("home_archetype", "unknown")
    away_arch = activation.get("away_archetype", "unknown")
    matchup_delta = _ARCHETYPE_MATCHUPS.get((home_arch, away_arch), 0.0)
    if matchup_delta == 0.0:
        matchup_delta = _ARCHETYPE_MATCHUPS.get((away_arch, home_arch), 0.0) * 0.8

    if matchup_delta > 2.0:
        score += matchup_delta
        supporting.append(
            f"Archetype matchup ({home_arch} vs {away_arch}) drives shot volume"
        )
    elif matchup_delta < -2.0:
        score += matchup_delta
        counter.append(
            f"Archetype matchup ({home_arch} vs {away_arch}) suppresses shot volume"
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

    return ShotsAnalysis(
        score=round(score, 2),
        environment=environment,
        supporting_mechanisms=supporting[:6],
        counter_mechanisms=counter[:4],
        active_chains=used_chains,
        active_scripts=used_scripts,
        direction=direction,
    )
