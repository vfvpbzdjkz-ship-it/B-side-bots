"""RETRO ROSTER — five earnest, lightweight retro chess engines on one harness.

Each engine is a small *strategy* (it only decides how to pick a move); everything
else — UCI handling, time budgeting, the legal-move safety net, the random
tiebreak — is shared. See ``RETRO_ROSTER_BUILD_SPEC`` for the full design.
"""

__version__ = "1.0.0"
