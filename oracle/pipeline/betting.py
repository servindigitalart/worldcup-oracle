"""
Match Betting Intelligence pipeline — Week 22.

Builds per-match multi-market signal cards from blended model probabilities
and (when available) Dixon-Coles scoreline grids.  Writes four artifacts.

Artifacts written:
  data/artifacts/match_betting_cards.json      one card per match (full markets)
  data/artifacts/betting_signals.json          flattened rows: one per signal
  data/artifacts/betting_summary.json          aggregate counts + disclaimer

Usage:
    python -m oracle.pipeline.betting
    make betting
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import polars as pl

from oracle.betting.markets import compute_all_markets
from oracle.betting.signals import build_betting_card, top_signals
from oracle.betting.schema import BetMarketProbability, MatchBettingCard

log = logging.getLogger(__name__)
_ARTIFACTS = Path("data/artifacts")
_SEED      = Path("data/seed")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_json(path: Path, fallback: object = None) -> object:
    if fallback is None:
        fallback = {}
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return fallback
    except Exception as exc:
        log.warning("Could not load %s: %s", path, exc)
        return fallback


def _load_parquet(path: Path) -> Optional[pl.DataFrame]:
    try:
        return pl.read_parquet(path)
    except FileNotFoundError:
        return None
    except Exception as exc:
        log.warning("Could not load %s: %s", path, exc)
        return None


def _fit_dixon_coles():
    """Fit and return DixonColesRatings, or None on failure."""
    try:
        from oracle.ratings.dixon_coles import DixonColesRatings
        from oracle.ingest.results import load_results
        df = load_results()
        dc = DixonColesRatings()
        dc.fit(df)
        return dc
    except Exception as exc:
        log.warning("Dixon-Coles fit failed — goal markets unavailable: %s", exc)
        return None


def _get_score_grid(dc, home_team: str, away_team: str):
    """Return 2D probability grid or None on failure."""
    if dc is None:
        return None
    try:
        grid_obj = dc.predict_grid(home_team, away_team, neutral=True)
        import numpy as np
        raw = np.maximum(grid_obj.grid, 0.0)
        total = raw.sum()
        if total <= 0:
            return None
        return raw / total
    except Exception:
        return None


def _build_fixture_index(seed_dir: Path) -> dict[str, dict]:
    """Return {match_id: {kickoff_at, venue, city, group}} from seed."""
    idx: dict[str, dict] = {}
    try:
        data = json.loads((seed_dir / "wc2026_fixtures.json").read_text())
        for f in data.get("fixtures", []):
            if f.get("stage") != "group":
                continue
            mid = f"{f['home_team']}_vs_{f['away_team']}"
            idx[mid] = {
                "kickoff_at": f.get("kickoff_at"),
                "venue":      f.get("venue"),
                "city":       f.get("city"),
                "group":      f.get("group", ""),
            }
    except Exception as exc:
        log.warning("Fixture seed load failed: %s", exc)
    return idx


def _result_status_index(artifacts_dir: Path) -> dict[str, str]:
    """Return {(home_vs_away, away_vs_home): status} from match_results."""
    idx: dict[str, str] = {}
    df = _load_parquet(artifacts_dir / "match_results.parquet")
    if df is not None:
        for row in df.iter_rows(named=True):
            key = f"{row['home_team']}_vs_{row['away_team']}"
            idx[key] = row["status"]
    return idx


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run(artifacts_dir: Path = _ARTIFACTS, seed_dir: Path = _SEED) -> dict:
    """Build betting intelligence artifacts. Returns summary dict."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    # ── 1. Load blended predictions (model 1X2 probs per match) ──────────────
    blend_df = _load_parquet(artifacts_dir / "blended_predictions.parquet")
    if blend_df is None or len(blend_df) == 0:
        log.warning(
            "blended_predictions.parquet not found. "
            "Run 'make blend' first."
        )
        _write_empty(artifacts_dir, ts)
        return {"n_matches": 0, "n_signals": 0, "n_with_dc_grid": 0}

    # ── 2. Load model-market comparison for market probs + gap ────────────────
    comp_df = _load_parquet(artifacts_dir / "model_market_comparison.parquet")
    comp_by_mid: dict[str, dict] = {}
    if comp_df is not None:
        for row in comp_df.iter_rows(named=True):
            comp_by_mid[row["match_id"]] = row

    # ── 3. Fixture index (kickoff_at, venue, city) ────────────────────────────
    fixture_idx = _build_fixture_index(seed_dir)

    # ── 4. Result status (to mark finished matches) ───────────────────────────
    result_idx = _result_status_index(artifacts_dir)

    # ── 5. Fit Dixon-Coles for scoreline grids ────────────────────────────────
    log.info("[betting] Fitting Dixon-Coles model for goal markets…")
    dc = _fit_dixon_coles()
    if dc is not None:
        log.info("[betting] Dixon-Coles ready.")
    else:
        log.warning("[betting] Dixon-Coles unavailable — goal markets skipped.")

    # ── 6. Build one betting card per match ───────────────────────────────────
    cards: list[MatchBettingCard] = []
    n_with_dc = 0

    for row in blend_df.iter_rows(named=True):
        mid       = row["match_id"]
        home_team = row["home_team"]
        away_team = row["away_team"]
        group     = row.get("group", "")
        home_prob = float(row.get("blend_home") or 0.0)
        draw_prob = float(row.get("blend_draw") or 0.0)
        away_prob = float(row.get("blend_away") or 0.0)
        has_mkt   = bool(row.get("has_market_data", False))

        comp = comp_by_mid.get(mid, {})
        mkt_home = comp.get("market_home")
        mkt_draw = comp.get("market_draw")
        mkt_away = comp.get("market_away")

        fix = fixture_idx.get(mid) or fixture_idx.get(f"{away_team}_vs_{home_team}") or {}
        kickoff_at = fix.get("kickoff_at")
        venue      = fix.get("venue")
        city       = fix.get("city")

        result_status = (
            result_idx.get(mid)
            or result_idx.get(f"{away_team}_vs_{home_team}")
        )
        is_finished = (result_status == "finished")

        score_grid = _get_score_grid(dc, home_team, away_team)
        if score_grid is not None:
            n_with_dc += 1

        markets = compute_all_markets(
            mid, home_prob, draw_prob, away_prob, score_grid,
            market_home=mkt_home,
            market_draw=mkt_draw,
            market_away=mkt_away,
            has_market_data=has_mkt,
            generated_at=ts,
        )

        card = build_betting_card(
            mid, group, home_team, away_team, markets,
            kickoff_at=kickoff_at,
            venue=venue,
            city=city,
            has_market_data=has_mkt,
            is_finished=is_finished,
            generated_at=ts,
        )
        cards.append(card)

    log.info(
        "[betting] Built %d betting cards (%d with DC goal markets).",
        len(cards), n_with_dc,
    )

    # ── 7. Write artifacts ────────────────────────────────────────────────────
    card_dicts = [c.to_dict() for c in cards]

    # 7a: match_betting_cards.json
    (artifacts_dir / "match_betting_cards.json").write_text(
        json.dumps(card_dicts, indent=2, default=str)
    )
    log.info("[betting] Wrote match_betting_cards.json (%d cards)", len(card_dicts))

    # 7b: betting_signals.json — flattened rows, only actionable signals
    signal_rows: list[dict] = []
    for card in cards:
        for m in card.top_signals:
            d = m.to_dict()
            d["home_team"]  = card.home_team
            d["away_team"]  = card.away_team
            d["group"]      = card.group
            d["kickoff_at"] = card.kickoff_at
            signal_rows.append(d)

    signal_rows.sort(key=lambda r: (
        # strong_signal first, then moderate, then watch
        {"strong_signal": 0, "moderate_signal": 1, "watch": 2}.get(r["signal_level"], 9),
        r.get("kickoff_at") or "",
    ))
    (artifacts_dir / "betting_signals.json").write_text(
        json.dumps(signal_rows, indent=2, default=str)
    )
    log.info("[betting] Wrote betting_signals.json (%d signals)", len(signal_rows))

    # 7c: betting_summary.json
    level_counts: dict[str, int] = defaultdict(int)
    for card in cards:
        for m in card.markets:
            level_counts[m.signal_level] += 1

    summary = {
        "generated_at":         ts,
        "n_matches":            len(cards),
        "n_with_dc_grid":       n_with_dc,
        "n_signals":            len(signal_rows),
        "n_strong_signal":      level_counts["strong_signal"],
        "n_moderate_signal":    level_counts["moderate_signal"],
        "n_watch":              level_counts["watch"],
        "n_no_signal":          level_counts["no_signal"],
        "n_model_only":         level_counts["model_probability_only"],
        "disclaimer": (
            "These are educational probability signals only. "
            "Not betting advice. "
            "A model-market gap does not imply value or a winning selection. "
            "Market odds may be more accurate than model estimates."
        ),
        "language_policy": {
            "forbidden_terms": [
                "guaranteed", "lock", "sure bet", "can't lose", "free money",
                "profit", "must bet", "bet this now", "high certainty", "risk-free",
            ],
        },
    }
    (artifacts_dir / "betting_summary.json").write_text(
        json.dumps(summary, indent=2, default=str)
    )
    log.info("[betting] Wrote betting_summary.json")

    log.info(
        "\n[betting] Summary:\n"
        "  Matches         : %d\n"
        "  DC goal markets : %d\n"
        "  Signals         : %d\n"
        "    strong_signal : %d\n"
        "    moderate      : %d\n"
        "    watch         : %d",
        len(cards), n_with_dc, len(signal_rows),
        level_counts["strong_signal"],
        level_counts["moderate_signal"],
        level_counts["watch"],
    )

    return {
        "n_matches":       len(cards),
        "n_with_dc_grid":  n_with_dc,
        "n_signals":       len(signal_rows),
    }


def _write_empty(artifacts_dir: Path, ts: str) -> None:
    for name, fallback in [
        ("match_betting_cards.json", []),
        ("betting_signals.json",     []),
        ("betting_summary.json", {
            "generated_at": ts,
            "n_matches": 0,
            "disclaimer": "No blended predictions available. Run 'make blend' first.",
        }),
    ]:
        (artifacts_dir / name).write_text(json.dumps(fallback, indent=2))


if __name__ == "__main__":
    run()
