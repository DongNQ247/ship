from __future__ import annotations


class DeployError(Exception):
    def __init__(self, message: str, reason: str = "", check: str = "", run: str = ""):
        full_msg = f"{message}: {reason}" if reason else message
        super().__init__(full_msg)
        self.message = message
        self.reason = reason
        self.check = check
        self.run = run
