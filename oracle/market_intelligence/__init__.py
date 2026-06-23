"""
Market Intelligence Engine — Week 28.

Builds explainable market models for corners, cards, and shots
using football mechanisms rather than historical averages.

Pipeline order: knowledge → knowledge_calibration → knowledge_learning
                → market_intelligence → thesis → export-web

Public interface:
    from oracle.market_intelligence.corners import analyze_corners
    from oracle.market_intelligence.cards   import analyze_cards
    from oracle.market_intelligence.shots   import analyze_shots
    from oracle.market_intelligence.signals import classify_signal
    from oracle.market_intelligence.explain import build_explanation
"""
