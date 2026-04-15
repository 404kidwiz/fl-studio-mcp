"""Structured error types for FL Studio MCP."""

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    MIDI_PORT_NOT_FOUND = "MIDI_PORT_NOT_FOUND"
    MIDI_CONNECT_FAILED = "MIDI_CONNECT_FAILED"
    NOT_CONNECTED = "NOT_CONNECTED"
    INVALID_PARAMS = "INVALID_PARAMS"
    FL_API_UNAVAILABLE = "FL_API_UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class FLMCPError(Exception):
    """Structured error with a machine-readable code and optional details."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.code.value,
            "message": self.message,
            "details": self.details,
        }

    def __str__(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2)
