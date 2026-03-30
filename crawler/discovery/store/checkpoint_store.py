from __future__ import annotations

from crawler.discovery.state.checkpoint import Checkpoint


class InMemoryCheckpointStore:
    def __init__(self) -> None:
        self.checkpoints: dict[str, Checkpoint] = {}

    def put(self, checkpoint_id: str, checkpoint: Checkpoint) -> Checkpoint:
        if checkpoint.checkpoint_id is not None and checkpoint.checkpoint_id != checkpoint_id:
            raise ValueError("checkpoint_id does not match checkpoint.checkpoint_id")
        self.checkpoints[checkpoint_id] = checkpoint
        return checkpoint

    def get(self, checkpoint_id: str) -> Checkpoint | None:
        return self.checkpoints.get(checkpoint_id)
