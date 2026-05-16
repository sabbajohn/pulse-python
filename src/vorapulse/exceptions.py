from __future__ import annotations


class PulseError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, response=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response


class PulseAuthenticationError(PulseError):
    pass


class PulseNotFoundError(PulseError):
    pass


class PulseRateLimitError(PulseError):
    pass


class PulseRemoteError(PulseError):
    pass


class PulseRequestError(PulseError):
    pass


class PulseValidationError(PulseRequestError):
    def __init__(self, message: str, errors: dict | None = None, status_code: int = 422, response=None):
        super().__init__(message, status_code, response)
        self.errors = errors or {}
