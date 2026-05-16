# vorapulse

Cliente Python/Flask para a API `v2` do VoraPulse.

## Instalacao

```bash
pip install vorapulse
```

Durante desenvolvimento interno, use um path install:

```bash
pip install -e packages/sabbajohn/pulse-python
```

## Uso Python

```python
from vorapulse import PulseClient

pulse = PulseClient("https://pulse.example.com", "api-token")
pulse.emails.send_sync({
    "to": [{"email": "cliente@example.com"}],
    "subject": "Bem-vindo",
    "html": "<p>Ola!</p>",
})

pulse.automations.trigger("pedido.criado", payload={"id": 123})
```

## Uso Flask

```python
from vorapulse.flask import PulseFlask

pulse = PulseFlask()

def create_app():
    app = Flask(__name__)
    app.config["PULSE_BASE_URL"] = "https://pulse.example.com"
    app.config["PULSE_API_TOKEN"] = "api-token"
    pulse.init_app(app)
    return app

pulse.client.automations.trigger("pedido.criado", payload={"id": 123})
```
