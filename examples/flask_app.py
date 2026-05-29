from flask import Flask

from vorapulse.flask import PulseFlask

pulse = PulseFlask()


def create_app():
    app = Flask(__name__)
    app.config["PULSE_BASE_URL"] = "https://pulse.example.com"
    app.config["PULSE_API_TOKEN"] = "api-token"
    pulse.init_app(app)
    return app
