from typing import Dict, Any, Optional
from app.helpers.error_codes import generate_error_code, ErrorCodeRegistry


class AppException(Exception):
    def __init__(
        self,
        status_code: int = 400,
        message: str = "An error occurred",
        errors: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.errors = errors or {}
        self.error_code = error_code


class ValidationException(AppException):
    def __init__(
        self,
        errors: Dict[str, Any],
        message: str = "Request validation failed",
        error_code: Optional[str] = ErrorCodeRegistry.VALIDATION_FAILED,
    ):
        super().__init__(status_code=422, message=message, errors=errors, error_code=error_code)


class AuthenticationException(AppException):
    def __init__(
        self,
        message: str = "Authentication failed",
        errors: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = ErrorCodeRegistry.AUTH_FAILED,
    ):
        if errors is None:
            errors = {"authentication": "Email or password is invalid"}
        super().__init__(status_code=401, message=message, errors=errors, error_code=error_code)


class AuthorizationException(AppException):
    def __init__(
        self,
        message: str = "Access denied",
        errors: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = ErrorCodeRegistry.FORBIDDEN,
    ):
        if errors is None:
            errors = {"authorization": "You do not have permission to access this resource"}
        super().__init__(status_code=403, message=message, errors=errors, error_code=error_code)


class NotFoundException(AppException):
    def __init__(
        self,
        message: str = "Resource not found",
        errors: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = ErrorCodeRegistry.NOT_FOUND,
    ):
        if errors is None:
            errors = {"resource": message}
        super().__init__(status_code=404, message=message, errors=errors, error_code=error_code)


class ConflictException(AppException):
    def __init__(
        self,
        message: str = "Resource conflict",
        errors: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = ErrorCodeRegistry.CONFLICT,
    ):
        if errors is None:
            errors = {"conflict": message}
        super().__init__(status_code=409, message=message, errors=errors, error_code=error_code)


class InternalException(AppException):
    def __init__(
        self,
        message: str = "An internal error occurred",
        errors: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        code = error_code or generate_error_code()
        formatted_message = f"{code}: {message}" if not message.startswith("ERR-") else message
        if errors is None:
            errors = {"server": "An internal error occurred"}
        super().__init__(status_code=500, message=formatted_message, errors=errors, error_code=code)


class AIServiceException(AppException):
    def __init__(
        self,
        status_code: int = 502,
        message: str = "AI service error",
        errors: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = ErrorCodeRegistry.AI_PROVIDER_ERROR,
    ):
        if errors is None:
            errors = {"ai": message}
        super().__init__(status_code=status_code, message=message, errors=errors, error_code=error_code)


class AIRateLimitException(AppException):
    def __init__(
        self,
        message: str = "AI rate limit exceeded",
        retry_after: Optional[int] = None,
        errors: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = ErrorCodeRegistry.AI_RATE_LIMITED,
    ):
        if errors is None:
            err_dict: Dict[str, Any] = {"ai": message}
            if retry_after is not None:
                err_dict["retry_after"] = retry_after
            errors = err_dict
        super().__init__(status_code=429, message=message, errors=errors, error_code=error_code)
        self.retry_after = retry_after


class AIConfigException(AppException):
    def __init__(
        self,
        message: str = "AI service is not configured",
        errors: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = ErrorCodeRegistry.AI_NOT_CONFIGURED,
    ):
        if errors is None:
            errors = {"ai": message}
        super().__init__(status_code=503, message=message, errors=errors, error_code=error_code)


class AgentTimeoutException(AppException):
    def __init__(
        self,
        message: str = "Agent request timed out",
        errors: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = ErrorCodeRegistry.AGENT_TIMEOUT,
    ):
        if errors is None:
            errors = {"agent": message}
        super().__init__(status_code=408, message=message, errors=errors, error_code=error_code)


class AgentCancelledException(AppException):
    def __init__(
        self,
        message: str = "Agent request cancelled by client",
        errors: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = ErrorCodeRegistry.AGENT_CANCELLED,
    ):
        if errors is None:
            errors = {"agent": message}
        super().__init__(status_code=499, message=message, errors=errors, error_code=error_code)
