"""
Knowledge Calibration Framework — Week 26.

Transforms expert-designed football knowledge into evidence-weighted knowledge.
Answers: "Which football mechanisms actually improve prediction quality?"

Stage 1 uses principled seed evidence (football analytics research + WC 2014/18/22
pattern estimates). Weights are conservative. Designed for live measurement in Stage 2.

Public interface:
    from oracle.knowledge_calibration.chains    import evaluate_chains
    from oracle.knowledge_calibration.scripts   import evaluate_scripts
    from oracle.knowledge_calibration.managers  import evaluate_managers
    from oracle.knowledge_calibration.archetypes import evaluate_archetypes
    from oracle.knowledge_calibration.scoring   import compute_value_score
    from oracle.knowledge_calibration.weights   import build_adaptive_weights
    from oracle.knowledge_calibration.report    import build_calibration_summary
"""
