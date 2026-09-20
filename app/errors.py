"""Application exceptions.

Each exception carries the HTTP status code it should map to. app/main.py registers
one handler that turns any RegFlowError into a JSON response: {"detail": "..."}.
"""


class RegFlowError(Exception):
    status_code = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ConfigError(RegFlowError):
    """A required environment variable is missing or invalid."""
    status_code = 500


class InvalidDocumentError(RegFlowError):
    """The upload is not a readable PDF (wrong type, empty, corrupt, too large, encrypted)."""
    status_code = 400


class DocumentNotFoundError(RegFlowError):
    status_code = 404


class DocumentExtractionError(RegFlowError):
    """The PDF opened, but no usable text could be extracted from it."""
    status_code = 422


class StorageError(RegFlowError):
    """Saving to / reading from S3 or local disk failed."""
    status_code = 502


class GeminiError(RegFlowError):
    """The Gemini API call failed or returned something unusable.

    The workflow catches this and falls back to Python-only checks, so it
    normally never reaches the client.
    """
    status_code = 503
