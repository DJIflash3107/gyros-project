import random
import string


def generate_error_code(prefix: str = "ERR-") -> str:
    """Generate a unique 5-digit traceable error code like ERR-67787."""
    code = "".join(random.choices(string.digits, k=5))
    return f"{prefix}{code}" if prefix else code


class ErrorCodeRegistry:
    COMMON_DB_ERROR = "ERR-60001"
    AUTH_FAILED = "ERR-40001"
    FORBIDDEN = "ERR-40003"
    NOT_FOUND = "ERR-40004"
    CONFLICT = "ERR-40009"
    VALIDATION_FAILED = "ERR-42200"
    INTERNAL_SERVER_ERROR = "ERR-50000"
    AI_BAD_REQUEST = "ERR-AI-400"
    AI_AUTH_FAILED = "ERR-AI-401"
    AI_FORBIDDEN = "ERR-AI-403"
    AI_RATE_LIMITED = "ERR-AI-429"
    AI_PROVIDER_ERROR = "ERR-AI-500"
    AI_CONNECTION_ERROR = "ERR-AI-503"
    AI_NOT_CONFIGURED = "ERR-AI-501"
    AGENT_BAD_REQUEST = "ERR-AGT-400"
    AGENT_TIMEOUT = "ERR-AGT-408"
    AGENT_RATE_LIMITED = "ERR-AGT-429"
    AGENT_CANCELLED = "ERR-AGT-499"
    AGENT_INTERNAL_ERROR = "ERR-AGT-500"
    AGENT_SERVICE_UNAVAILABLE = "ERR-AGT-503"
