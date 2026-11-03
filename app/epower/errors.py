"""Exception hierarchy shared by all modules."""


class CCNUEWError(RuntimeError):
    """Base exception for all CCNU Electricity Watch errors."""


class ConfigError(CCNUEWError):
    """Missing or invalid configuration: credentials, floor, target room."""


class NetworkError(CCNUEWError):
    """Transient network failure: timeout, connection reset, DNS failure."""


class AuthError(CCNUEWError):
    """Authentication failure: expired JWT, rejected login, SM2 mismatch."""


class APIError(CCNUEWError):
    """Upstream API returned a non-zero code."""


class ParseError(CCNUEWError):
    """Response body is malformed or has an unexpected schema."""


class NotFoundError(CCNUEWError):
    """Building, room, or meter is missing or ambiguous."""
