"""Value-free errors for enterprise adapters."""

import re


class GovernanceError(RuntimeError):
    def __init__(self, code: str):
        if not re.fullmatch(r"[a-z][a-z_]{1,63}", code):
            raise ValueError("invalid governance error code")
        self.code = code
        super().__init__(code)
