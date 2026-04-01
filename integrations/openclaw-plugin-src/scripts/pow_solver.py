from __future__ import annotations

from typing import Any


class UnsupportedChallenge(RuntimeError):
    def __init__(self, challenge_type: str) -> None:
        super().__init__(f"unsupported challenge type: {challenge_type}")


def solve_challenge(challenge: dict[str, Any]) -> str:
    """Attempt to solve a platform challenge.

    Raises UnsupportedChallenge for all types that have no real solver
    implementation yet. Callers should catch UnsupportedChallenge and
    route the item to a skip/retry queue.
    """
    challenge_type = str(challenge.get("question_type") or "unknown")
    # No challenge types are currently solvable — all require a real
    # implementation before they can be accepted.
    raise UnsupportedChallenge(challenge_type)
