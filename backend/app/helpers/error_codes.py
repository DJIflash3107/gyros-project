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
