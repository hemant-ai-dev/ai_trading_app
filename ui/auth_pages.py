"""Compatibility shim — login lives in ui.auth."""

from ui.auth import current_user, logout, render_auth_gate

__all__ = ["current_user", "logout", "render_auth_gate"]
