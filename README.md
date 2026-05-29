# vorapulse

Python and Flask client for the public `v2` VoraPulse API.

## Contract

The public contract is defined by:

- `https://github.com/vora-sys/Pulse/blob/main/VoraPulse/docs/openapi/pulse-public-v2.openapi.json`

Internal or administrative endpoints are intentionally out of scope.

## Compatibility

- Python `>=3.9`
- Public API base: `/api/v2`

## Installation

```bash
pip install vorapulse
```

For Flask projects:

```bash
pip install "vorapulse[flask]"
```

For local development:

```bash
pip install -e packages/sabbajohn/pulse-python
```

## Quickstart

```python
from vorapulse import PulseClient

pulse = PulseClient("https://pulse.example.com", "api-token")

pulse.get("health")

pulse.emails.send_sync({
    "to": [{"email": "cliente@example.com"}],
    "subject": "Bem-vindo",
    "html": "<p>Ola!</p>",
})

pulse.automations.trigger("pedido.criado", payload={"pedido_id": 123})
```

The client automatically normalizes the base URL to `/api/v2`.

## Flask adapter

```python
from flask import Flask
from vorapulse.flask import PulseFlask

pulse = PulseFlask()

def create_app():
    app = Flask(__name__)
    app.config["PULSE_BASE_URL"] = "https://pulse.example.com"
    app.config["PULSE_API_TOKEN"] = "api-token"
    pulse.init_app(app)
    return app
```

Legacy aliases remain supported:

```env
PULSE_VORA_BASE_URL=https://pulse.example.com
PULSE_VORA_TOKEN=api-token
PULSE_VORA_TIMEOUT=30
```

## Services

- `emails`
- `templates`
- `composer`
- `campaigns`
- `audiences`
- `automations`
- `calendar`
- `whatsapp`

## Errors

- `PulseAuthenticationError`
- `PulseNotFoundError`
- `PulseValidationError`
- `PulseRateLimitError`
- `PulseRemoteError`
- `PulseRequestError`

## Examples

- `examples/quickstart.py`
- `examples/flask_app.py`
