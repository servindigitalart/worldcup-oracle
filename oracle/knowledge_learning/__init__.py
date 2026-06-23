"""
Adaptive Knowledge Learning System — Week 27.

Converts Oracle from historically-calibrated to continuously-calibrated
while remaining deterministic, auditable, and conservative.

Design principles:
  - One match never radically changes a weight
  - Historical evidence dominates; recent evidence nudges
  - Every update is reproducible and logged
  - All weight changes bounded: ±0.03/cycle, ±0.10/month, [0.50, 1.50] absolute
  - No ML, no neural networks, no black-box updates

Pipeline order: knowledge → knowledge_calibration → knowledge_learning → thesis

Public interface:
    from oracle.knowledge_learning.evidence  import build_evidence_log
    from oracle.knowledge_learning.outcomes  import evaluate_outcomes
    from oracle.knowledge_learning.scoring   import compute_contributions
    from oracle.knowledge_learning.updater   import compute_weight_updates
    from oracle.knowledge_learning.history   import build_learning_history
    from oracle.knowledge_learning.report    import build_learning_report
"""
