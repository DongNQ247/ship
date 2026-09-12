from __future__ import annotations

import os
from pathlib import Path


def find_project_root(start: Path | None = None) -> Path | None:
    """Find the root directory containing .ship by traversing upwards."""
    current = (start or Path.cwd()).resolve()
    for parent in [current, *current.parents]:
        if (parent / ".ship").is_dir():
            return parent
    return None


class ShipContext:
    def __init__(self, root: Path | None = None):
        if root is not None:
            self._root = root.resolve()
        else:
            found = find_project_root()
            self._root = found if found is not None else Path.cwd().resolve()

    @property
    def root_dir(self) -> Path:
        return self._root

    @property
    def ship_dir(self) -> Path:
        return self._root / ".ship"

    @property
    def config_file(self) -> Path:
        return self.ship_dir / "config.env"

    @property
    def guardrail_dir(self) -> Path:
        return self.ship_dir / "guardrails"

    @property
    def allowed_file(self) -> Path:
        return self.guardrail_dir / "allowed"

    @property
    def deny_file(self) -> Path:
        return self.guardrail_dir / "deny"

    @property
    def protected_file(self) -> Path:
        return self.guardrail_dir / "protected"

    @property
    def state_dir(self) -> Path:
        return self.ship_dir / "state"

    @property
    def staging_file(self) -> Path:
        return self.state_dir / "files"

    @property
    def ignore_file(self) -> Path:
        return self.root_dir / ".shipignore"

    @property
    def required_files(self) -> tuple[Path, ...]:
        return (
            self.config_file,
            self.allowed_file,
            self.deny_file,
            self.protected_file,
            self.staging_file,
        )


_active_context: ShipContext | None = None


def get_context(root: Path | None = None) -> ShipContext:
    global _active_context
    if root is not None:
        return ShipContext(root)
    if _active_context is None:
        _active_context = ShipContext()
    return _active_context


def set_context(context: ShipContext | None) -> None:
    global _active_context
    _active_context = context


# Module-level dynamic attribute resolution for backward compatibility
def __getattr__(name: str):
    ctx = get_context()
    if name == "ROOT_DIR":
        return ctx.root_dir
    if name == "SHIP_DIR" or name == "SCRIPT_DIR":
        return ctx.ship_dir
    if name == "CONFIG_FILE":
        return ctx.config_file
    if name == "GUARDRAIL_DIR":
        return ctx.guardrail_dir
    if name == "ALLOWED_FILE":
        return ctx.allowed_file
    if name == "DENY_FILE":
        return ctx.deny_file
    if name == "PROTECTED_FILE":
        return ctx.protected_file
    if name == "STATE_DIR":
        return ctx.state_dir
    if name == "STAGING_FILE":
        return ctx.staging_file
    if name == "IGNORE_FILE":
        return ctx.ignore_file
    if name == "REQUIRED_FILES":
        return ctx.required_files
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
