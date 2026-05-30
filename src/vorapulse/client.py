from __future__ import annotations

import json
from typing import Any
from urllib import error, parse, request

from .exceptions import (
    PulseAuthenticationError,
    PulseError,
    PulseNotFoundError,
    PulseRateLimitError,
    PulseRemoteError,
    PulseRequestError,
    PulseValidationError,
)


class PulseClient:
    SDK_USER_AGENT = "vorapulse/0.1.2"

    def __init__(self, base_url: str, api_token: str, *, timeout: int = 30):
        self.base_url = self._normalize_base_url(base_url)
        self.api_token = str(api_token or "").strip()
        self.timeout = int(timeout or 30)
        self.emails = EmailService(self)
        self.templates = TemplateService(self)
        self.composer = ComposerService(self)
        self.campaigns = CampaignService(self)
        self.audiences = AudienceService(self)
        self.contacts = ContactService(self)
        self.automations = AutomationService(self)
        self.calendar = CalendarService(self)
        self.whatsapp = WhatsAppService(self)

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_token)

    def get(self, endpoint: str, query: dict[str, Any] | None = None):
        return self.request("GET", endpoint, query=query)

    def post(self, endpoint: str, payload: dict[str, Any] | None = None):
        return self.request("POST", endpoint, payload=payload or {})

    def patch(self, endpoint: str, payload: dict[str, Any] | None = None):
        return self.request("PATCH", endpoint, payload=payload or {})

    def put(self, endpoint: str, payload: dict[str, Any] | None = None):
        return self.request("PUT", endpoint, payload=payload or {})

    def delete(self, endpoint: str, payload: dict[str, Any] | None = None):
        return self.request("DELETE", endpoint, payload=payload)

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ):
        if not self.is_configured:
            raise PulseAuthenticationError("Pulse client is not configured.")

        url = self._url(endpoint, query)
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(url, method=method.upper(), data=body)
        req.add_header("Accept", "application/json")
        req.add_header("Authorization", f"Bearer {self.api_token}")
        req.add_header("User-Agent", self.SDK_USER_AGENT)

        if body is not None:
            req.add_header("Content-Type", "application/json")

        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                return self._parse_response(response.getcode(), raw)
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            return self._parse_response(exc.code, raw)
        except error.URLError as exc:
            raise PulseRequestError(f"Pulse connection failed: {exc.reason}") from exc

    def _url(self, endpoint: str, query: dict[str, Any] | None = None) -> str:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if query:
            url = f"{url}?{parse.urlencode(query, doseq=True)}"
        return url

    def _parse_response(self, status_code: int, raw: str):
        payload = None
        if raw:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                if status_code >= 400:
                    raise PulseRemoteError(raw, status_code, raw) from exc
                raise PulseRemoteError("Pulse returned a non-JSON response.", status_code, raw) from exc
        else:
            payload = {}

        if status_code < 400:
            return payload

        message = "Pulse request failed."
        if isinstance(payload, dict):
            message = payload.get("message") or payload.get("error") or message
        elif isinstance(payload, str):
            message = payload

        if status_code in (401, 403):
            raise PulseAuthenticationError(message, status_code, payload)
        if status_code == 404:
            raise PulseNotFoundError(message, status_code, payload)
        if status_code == 422:
            errors = payload.get("errors", {}) if isinstance(payload, dict) else {}
            raise PulseValidationError(message, errors, status_code, payload)
        if status_code == 429:
            raise PulseRateLimitError(message, status_code, payload)
        if status_code >= 500:
            raise PulseRemoteError(message, status_code, payload)
        raise PulseRequestError(message, status_code, payload)

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        value = str(base_url or "").strip().rstrip("/")
        if not value:
            return ""
        if not value.endswith("/api/v2"):
            value = f"{value}/api/v2"
        return value


class BaseService:
    def __init__(self, client: PulseClient):
        self.client = client


class EmailService(BaseService):
    def send_sync(self, payload: dict[str, Any]):
        return self.client.post("emails/send-sync", payload)

    def send_async(self, payload: dict[str, Any]):
        return self.client.post("emails/send-async", payload)

    def send(self, payload: dict[str, Any]):
        return self.client.post("emails", payload)

    def list(self, query: dict[str, Any] | None = None):
        return self.client.get("emails", query or {})

    def status(self, email_id: int | str):
        return self.client.get(f"emails/{email_id}")

    def cancel(self, email_id: int | str):
        return self.client.delete(f"emails/{email_id}")

    def retry(self, email_id: int | str):
        return self.client.post(f"emails/{email_id}/retry")

    def stats(self):
        return self.client.get("stats")

    def test_smtp(self, payload: dict[str, Any]):
        return self.client.post("smtp/test", payload)


class TemplateService(BaseService):
    def meta(self):
        return self.client.get("templates/meta")

    def list(self, query: dict[str, Any] | None = None):
        return self.client.get("templates", query or {})

    def create(self, payload: dict[str, Any]):
        return self.client.post("templates", payload)

    def show(self, template_id: int | str):
        return self.client.get(f"templates/{template_id}")

    def update(self, template_id: int | str, payload: dict[str, Any]):
        return self.client.patch(f"templates/{template_id}", payload)

    def delete(self, template_id: int | str):
        return self.client.delete(f"templates/{template_id}")

    def preview(self, payload: dict[str, Any]):
        return self.client.post("templates/preview", payload)


class ComposerService(BaseService):
    def meta(self):
        return self.client.get("composer/meta")

    def render(self, payload: dict[str, Any]):
        return self.client.post("composer/render", payload)

    def validate(self, payload: dict[str, Any]):
        return self.client.post("composer/validate", payload)

    def autosave(self, payload: dict[str, Any]):
        return self.client.post("composer/autosave", payload)

    def latest_revision(self, query: dict[str, Any] | None = None):
        return self.client.get("composer/revision", query or {})


class CampaignService(BaseService):
    def list(self, query: dict[str, Any] | None = None):
        return self.client.get("campaigns", query or {})

    def create(self, payload: dict[str, Any]):
        return self.client.post("campaigns", payload)

    def preview(self, payload: dict[str, Any]):
        return self.client.post("campaigns/preview", payload)

    def show(self, campaign_id: int | str):
        return self.client.get(f"campaigns/{campaign_id}")

    def send(self, campaign_id: int | str, payload: dict[str, Any] | None = None):
        return self.client.post(f"campaigns/{campaign_id}/send", payload or {})


class AudienceService(BaseService):
    def list(self, query: dict[str, Any] | None = None):
        return self.client.get("audiences", query or {})

    def create(self, payload: dict[str, Any]):
        return self.client.post("audiences", payload)

    def show(self, audience_id: int | str):
        return self.client.get(f"audiences/{audience_id}")

    def update(self, audience_id: int | str, payload: dict[str, Any]):
        return self.client.patch(f"audiences/{audience_id}", payload)

    def delete(self, audience_id: int | str):
        return self.client.delete(f"audiences/{audience_id}")

    def channels(self, query: dict[str, Any] | None = None):
        return self.client.get("audience/channels", query or {})

    def members(self, query: dict[str, Any] | None = None):
        return self.client.get("audience/members", query or {})

    def create_member(self, payload: dict[str, Any]):
        return self.client.post("audience/members", payload)

    def member(self, member_id: int | str):
        return self.client.get(f"audience/members/{member_id}")

    def update_member(self, member_id: int | str, payload: dict[str, Any]):
        return self.client.patch(f"audience/members/{member_id}", payload)

    def delete_member(self, member_id: int | str):
        return self.client.delete(f"audience/members/{member_id}")

    def transition_member(self, member_id: int | str, payload: dict[str, Any]):
        return self.client.post(f"audience/members/{member_id}/transition", payload)

    def tags(self, query: dict[str, Any] | None = None):
        return self.client.get("audience/tags", query or {})

    def segments(self, query: dict[str, Any] | None = None):
        return self.client.get("audience/segments", query or {})


class ContactService(BaseService):
    def list(self, query: dict[str, Any] | None = None):
        return self.client.get("contacts", query or {})

    def create(self, payload: dict[str, Any]):
        return self.client.post("contacts", payload)

    def show(self, contact_id: int | str):
        return self.client.get(f"contacts/{contact_id}")

    def update(self, contact_id: int | str, payload: dict[str, Any]):
        return self.client.patch(f"contacts/{contact_id}", payload)

    def replace(self, contact_id: int | str, payload: dict[str, Any]):
        return self.client.put(f"contacts/{contact_id}", payload)

    def delete(self, contact_id: int | str):
        return self.client.delete(f"contacts/{contact_id}")


class AutomationService(BaseService):
    def list(self, query: dict[str, Any] | None = None):
        return self.client.get("automations", query or {})

    def create(self, payload: dict[str, Any]):
        return self.client.post("automations", payload)

    def trigger(
        self,
        event_name: str,
        *,
        payload: dict[str, Any] | None = None,
        contact: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ):
        body = {
            "event_name": event_name,
            "payload": payload or {},
            "contact": contact,
            "context": context,
        }
        return self.client.post("automations/trigger", {k: v for k, v in body.items() if v is not None})

    def show(self, automation_id: int | str):
        return self.client.get(f"automations/{automation_id}")

    def update(self, automation_id: int | str, payload: dict[str, Any]):
        return self.client.patch(f"automations/{automation_id}", payload)

    def delete(self, automation_id: int | str):
        return self.client.delete(f"automations/{automation_id}")

    def toggle(self, automation_id: int | str):
        return self.client.post(f"automations/{automation_id}/toggle")

    def run(self, automation_id: int | str, payload: dict[str, Any] | None = None):
        return self.client.post(f"automations/{automation_id}/run", payload or {})


class CalendarService(BaseService):
    def items(self, query: dict[str, Any] | None = None):
        return self.client.get("calendar/items", query or {})

    def create_event(self, payload: dict[str, Any]):
        return self.client.post("calendar/events", payload)

    def delete_event(self, event_id: int | str):
        return self.client.delete(f"calendar/events/{event_id}")


class WhatsAppService(BaseService):
    def config(self):
        return self.client.get("whatsapp/config")

    def update_config(self, payload: dict[str, Any]):
        return self.client.patch("whatsapp/config", payload)

    def test_config(self, payload: dict[str, Any] | None = None):
        return self.client.post("whatsapp/config/test", payload or {})

    def instance_status(self):
        return self.client.get("whatsapp/instance/status")

    def generate_qr(self, payload: dict[str, Any] | None = None):
        return self.client.post("whatsapp/instance/qr", payload or {})

    def configure_webhook(self, payload: dict[str, Any] | None = None):
        return self.client.post("whatsapp/instance/webhook", payload or {})

    def restart_instance(self, payload: dict[str, Any] | None = None):
        return self.client.post("whatsapp/instance/restart", payload or {})

    def messages(self, query: dict[str, Any] | None = None):
        return self.client.get("whatsapp/messages", query or {})

    def send_message(self, payload: dict[str, Any]):
        return self.client.post("whatsapp/messages/send", payload)
