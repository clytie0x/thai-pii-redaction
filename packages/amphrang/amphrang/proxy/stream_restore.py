"""SDK adapter for the canonical guarded incremental restorer."""

from pii_redactor.restore_context import GuardedStreamRestorer


class StreamRestorer(GuardedStreamRestorer):
    """Preserve the proxy API while the shared core owns restoration policy."""
