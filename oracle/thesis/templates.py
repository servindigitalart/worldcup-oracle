"""
Betting Thesis Templates — Week 25D MVP.

Deterministic template filling. No LLM calls. All text is generated from
structured data using pattern-matched templates.

Language policy: safe terms only.
  OK:  signal detected, model edge, watchlist, market aligned, high variance,
       insufficient data, model estimate, no market benchmark
  FORBIDDEN: bet this, lock, guaranteed, profit, sure thing, risk-free
"""
from __future__ import annotations

from typing import Optional


def _pct(p: float) -> str:
    return f"{round(p * 100, 1)}%"


def _odds(p: float) -> str:
    if p <= 0:
        return "—"
    return f"{round(1.0 / p, 2)}"


def _selection_label(selection: str, home_team: str, away_team: str) -> str:
    """Convert selection key to human-readable label."""
    m = {
        "home_win":     home_team.replace("_", " ").title(),
        "away_win":     away_team.replace("_", " ").title(),
        "draw":         "Draw",
        "home_or_draw": f"{home_team.replace('_', ' ').title()} or Draw",
        "draw_or_away": f"Draw or {away_team.replace('_', ' ').title()}",
        "home_or_away": f"{home_team.replace('_', ' ').title()} or {away_team.replace('_', ' ').title()}",
        "over":         "Over",
        "under":        "Under",
        "yes":          "BTTS Yes",
        "no":           "BTTS No",
    }
    return m.get(selection, selection.replace("_", " ").title())


def _market_label(market_type: str, line: Optional[float] = None) -> str:
    labels = {
        "1x2":          "1X2",
        "double_chance": "Double Chance",
        "draw_no_bet":   "Draw No Bet",
        "btts":          "Both Teams to Score",
        "correct_score": "Correct Score",
    }
    if market_type.startswith("over_under") and line is not None:
        return f"Over/Under {line}"
    return labels.get(market_type, market_type.replace("_", " ").title())


# ── Template dispatchers ───────────────────────────────────────────────────────

def build_explanation(
    market_type: str,
    selection: str,
    line: Optional[float],
    model_probability: float,
    market_implied_probability: Optional[float],
    raw_edge: Optional[float],
    contrarian_classification: str,
    home_team: str,
    away_team: str,
    confidence_label: str,
) -> tuple[str, str, str]:
    """
    Return (headline, body, key_risk_statement) for a thesis.
    """
    sel_label = _selection_label(selection, home_team, away_team)
    mkt_label = _market_label(market_type, line)
    home = home_team.replace("_", " ").title()
    away = away_team.replace("_", " ").title()

    if contrarian_classification == "aligned":
        return _aligned_template(sel_label, mkt_label, model_probability)

    if contrarian_classification == "model_only":
        return _model_only_template(
            market_type, selection, line, sel_label, mkt_label,
            model_probability, home, away,
        )

    # Market-comparison templates (slight/moderate/strong/extreme edge)
    return _market_edge_template(
        market_type, selection, line, sel_label, mkt_label,
        model_probability, market_implied_probability, raw_edge,
        contrarian_classification, home, away, confidence_label,
    )


def _aligned_template(
    sel_label: str,
    mkt_label: str,
    model_probability: float,
) -> tuple[str, str, str]:
    headline = f"{mkt_label} — {sel_label}: model aligned with market"
    body = (
        f"Oracle's estimate for {sel_label} ({_pct(model_probability)}) is broadly "
        f"aligned with the current market price. No meaningful model-market gap is "
        f"detected in this market. The model and market are reading this similarly."
    )
    risk = "Market alignment suggests the model has no informational edge here."
    return headline, body, risk


def _model_only_template(
    market_type: str,
    selection: str,
    line: Optional[float],
    sel_label: str,
    mkt_label: str,
    model_probability: float,
    home: str,
    away: str,
) -> tuple[str, str, str]:
    if market_type == "1x2":
        headline = f"{mkt_label} — {sel_label}: model estimate {_pct(model_probability)}"
        if selection == "home_win":
            team = home
        elif selection == "away_win":
            team = away
        else:
            team = "a draw"
        body = (
            f"Oracle's blended model (Elo + Dixon-Coles) estimates the probability of "
            f"{sel_label} at {_pct(model_probability)} (fair odds {_odds(model_probability)}). "
            f"No market benchmark is currently available for direct comparison, so this is "
            f"a model-only watchlist signal — not a market edge assessment. "
            f"The signal reflects Oracle's assessment of {home} vs {away} based on "
            f"historical performance ratings and scoring patterns."
        )
        risk = (
            "No market data is available to validate this estimate. "
            "The model carries inherent uncertainty and market odds, when available, "
            "may reflect information not present in the model."
        )

    elif market_type == "double_chance":
        headline = f"{mkt_label} — {sel_label}: model estimate {_pct(model_probability)}"
        body = (
            f"Oracle's model estimates the Double Chance for {sel_label} at "
            f"{_pct(model_probability)} — derived algebraically from the 1X2 probability "
            f"distribution. No market benchmark is available for comparison. "
            f"This is a model-only watchlist signal."
        )
        risk = "Derived market — dependent on 1X2 accuracy. No market validation available."

    elif market_type == "draw_no_bet":
        headline = f"{mkt_label} — {sel_label}: model estimate {_pct(model_probability)}"
        body = (
            f"Oracle's Draw No Bet estimate for {sel_label} is {_pct(model_probability)}, "
            f"derived by renormalising the 1X2 home/away probabilities with the draw "
            f"outcome removed. No market benchmark is available. "
            f"This is a model-only watchlist signal."
        )
        risk = "Derived market — accuracy depends on 1X2 model. No market validation available."

    elif market_type.startswith("over_under") and line is not None:
        direction = "over" if selection == "over" else "under"
        headline = f"{mkt_label} — {sel_label} {line}: model estimate {_pct(model_probability)}"
        body = (
            f"Oracle's Dixon-Coles scoring model estimates {direction} {line} total goals "
            f"at {_pct(model_probability)} for {home} vs {away}. "
            f"This probability is derived from the full 10×10 scoreline grid based on "
            f"each team's attack and defence ratings. No market odds are available for "
            f"direct comparison — this is a model-only watchlist signal."
        )
        risk = (
            "Model-only estimate. Scoring model uncertainty is higher than 1X2 uncertainty. "
            "Market odds, when available, may reflect team news not captured here."
        )

    elif market_type == "btts":
        direction = "both teams to score" if selection == "yes" else "at least one team to keep a clean sheet"
        headline = f"BTTS {sel_label}: model estimate {_pct(model_probability)}"
        body = (
            f"Oracle's scoring model estimates the probability of {direction} at "
            f"{_pct(model_probability)} for {home} vs {away}. "
            f"The estimate is derived from the Dixon-Coles joint scoring distribution, "
            f"which models each team's attack and defence independently. "
            f"No market benchmark is available — model-only watchlist signal."
        )
        risk = (
            "BTTS markets are sensitive to defensive form and team news (injuries to key "
            "attackers or defenders) not yet captured in the model."
        )

    elif market_type == "correct_score":
        headline = f"Correct Score {sel_label}: model estimate {_pct(model_probability)}"
        body = (
            f"Oracle's Dixon-Coles model assigns {_pct(model_probability)} probability "
            f"to the {sel_label} scoreline for {home} vs {away}. "
            f"Correct score markets carry very high variance — this is a low-confidence "
            f"model-only signal that should be treated as illustrative only."
        )
        risk = (
            "Correct score markets have high intrinsic variance. Even accurate probability "
            "models produce unreliable correct-score predictions due to the large number "
            "of possible outcomes."
        )

    else:
        headline = f"{mkt_label} — {sel_label}: model estimate {_pct(model_probability)}"
        body = (
            f"Oracle's model estimates {sel_label} at {_pct(model_probability)}. "
            f"No market data available — model-only watchlist signal."
        )
        risk = "No market data available. Model estimate only."

    return headline, body, risk


def _market_edge_template(
    market_type: str,
    selection: str,
    line: Optional[float],
    sel_label: str,
    mkt_label: str,
    model_probability: float,
    market_implied_probability: Optional[float],
    raw_edge: Optional[float],
    contrarian_classification: str,
    home: str,
    away: str,
    confidence_label: str,
) -> tuple[str, str, str]:
    assert market_implied_probability is not None
    assert raw_edge is not None

    edge_abs = abs(raw_edge)
    direction = "above" if raw_edge > 0 else "below"
    edge_label = {
        "slight_edge":   "slight signal detected",
        "moderate_edge": "moderate signal detected",
        "strong_edge":   "strong signal detected",
        "extreme_edge":  "strong signal detected — high uncertainty",
    }.get(contrarian_classification, "signal detected")

    confidence_hedge = {
        "very_high": "The model is highly confident in this estimate.",
        "high":      "The model has reasonable confidence in this estimate.",
        "medium":    "The model has moderate confidence. Treat as a watchlist signal.",
        "low":       "Confidence is limited. This is a watchlist-only signal.",
        "very_low":  "Very limited confidence. Treat as speculative only.",
    }.get(confidence_label, "")

    if market_type == "1x2":
        if selection == "home_win":
            team = home
        elif selection == "away_win":
            team = away
        else:
            team = "Draw"
        headline = (
            f"1X2 — {sel_label}: {edge_label} "
            f"({_pct(model_probability)} model vs {_pct(market_implied_probability)} market)"
        )
        body = (
            f"Oracle sees {sel_label} at {_pct(model_probability)} versus the market's "
            f"{_pct(market_implied_probability)} implied probability — a {_pct(edge_abs)} gap "
            f"{direction} market. The signal comes from the Elo/Dixon-Coles blended model's "
            f"assessment of {home} vs {away} relative to what the current market prices. "
            f"{confidence_hedge}"
        )
        risk = (
            "The model may not reflect the latest team news, injury updates, or tactical "
            "considerations that professional market makers have already incorporated. "
            "A model-market gap is not evidence of value — the market may be more accurate."
        )

    elif market_type.startswith("over_under") and line is not None:
        headline = (
            f"O/U {line} — {sel_label}: {edge_label} "
            f"({_pct(model_probability)} vs {_pct(market_implied_probability)})"
        )
        body = (
            f"Oracle's Dixon-Coles model estimates {selection} {line} goals at "
            f"{_pct(model_probability)} for {home} vs {away}. "
            f"The market implies {_pct(market_implied_probability)} — a gap of "
            f"{_pct(edge_abs)} {direction} the market estimate. "
            f"{confidence_hedge}"
        )
        risk = (
            "Goals markets are sensitive to team news (attacking/defensive personnel changes) "
            "that the model does not yet capture. The gap may reflect information the "
            "model lacks rather than a genuine pricing inefficiency."
        )

    elif market_type == "btts":
        headline = (
            f"BTTS {sel_label}: {edge_label} "
            f"({_pct(model_probability)} vs {_pct(market_implied_probability)})"
        )
        body = (
            f"Oracle's scoring model estimates BTTS {sel_label} at {_pct(model_probability)} "
            f"versus the market's {_pct(market_implied_probability)} — a "
            f"{_pct(edge_abs)} gap {direction} market for {home} vs {away}. "
            f"{confidence_hedge}"
        )
        risk = (
            "BTTS markets are sensitive to defensive injuries and team selection that "
            "the model may not yet reflect. The market may be more accurate."
        )

    elif market_type == "double_chance":
        headline = (
            f"Double Chance — {sel_label}: {edge_label} "
            f"({_pct(model_probability)} vs {_pct(market_implied_probability)})"
        )
        body = (
            f"Oracle estimates the Double Chance for {sel_label} at {_pct(model_probability)} "
            f"versus the market's {_pct(market_implied_probability)} — a gap of "
            f"{_pct(edge_abs)} {direction} market. This is derived from the Oracle 1X2 "
            f"distribution for {home} vs {away}. {confidence_hedge}"
        )
        risk = "Accuracy depends on the underlying 1X2 model. Market may be more accurate."

    elif market_type == "draw_no_bet":
        headline = (
            f"Draw No Bet — {sel_label}: {edge_label} "
            f"({_pct(model_probability)} vs {_pct(market_implied_probability)})"
        )
        body = (
            f"Oracle's Draw No Bet estimate for {sel_label} is {_pct(model_probability)} "
            f"versus the market's {_pct(market_implied_probability)} — a gap of "
            f"{_pct(edge_abs)} {direction} market for {home} vs {away}. "
            f"{confidence_hedge}"
        )
        risk = "Derived from 1X2 model. The market may be more accurate."

    else:
        headline = (
            f"{mkt_label} — {sel_label}: {edge_label} "
            f"({_pct(model_probability)} vs {_pct(market_implied_probability)})"
        )
        body = (
            f"Oracle estimates {sel_label} at {_pct(model_probability)} versus "
            f"the market's {_pct(market_implied_probability)}. "
            f"Gap: {_pct(edge_abs)} {direction} market. {confidence_hedge}"
        )
        risk = "Model-market comparison. The market may incorporate information the model lacks."

    # Extreme edge safety note
    if contrarian_classification == "extreme_edge":
        body += (
            " Note: this is a large model-market gap. Extreme gaps sometimes indicate "
            "model error or stale market data rather than a genuine inefficiency. "
            "Treat with caution."
        )

    return headline, body, risk
