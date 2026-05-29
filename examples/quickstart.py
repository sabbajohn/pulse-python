from vorapulse import PulseClient

pulse = PulseClient("https://pulse.example.com", "api-token")

print(pulse.get("health"))
