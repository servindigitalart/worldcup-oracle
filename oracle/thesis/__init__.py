"""
Betting Thesis Engine — Week 25D MVP.

Converts Oracle model probabilities and market comparison data into
structured, ranked betting theses with human-readable explanations.

Stage 1 scope: uses only existing artifacts (blended predictions + match
betting cards). No Stage 2 API-Football, player props, cards, or shots.

Language policy: same as oracle.betting.schema.FORBIDDEN_TERMS.
All thesis text is checked against this policy at construction time.
"""
