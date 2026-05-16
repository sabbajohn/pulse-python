from __future__ import annotations

from flask import current_app

from .client import PulseClient


class PulseFlask:
    def __init__(self, app=None):
        self.app = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.extensions = getattr(app, "extensions", {})
        app.extensions["vorapulse"] = self
        self.app = app

    @property
    def client(self) -> PulseClient:
        app = self.app or current_app
        base_url = app.config.get("PULSE_BASE_URL") or app.config.get("PULSE_VORA_BASE_URL") or ""
        api_token = app.config.get("PULSE_API_TOKEN") or app.config.get("PULSE_VORA_TOKEN") or ""
        timeout = app.config.get("PULSE_TIMEOUT") or app.config.get("PULSE_VORA_TIMEOUT") or 30
        return PulseClient(base_url, api_token, timeout=int(timeout))
