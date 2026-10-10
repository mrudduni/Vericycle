class ApiError(Exception):
    """Maps to {"error": {"code", "message"}} with an HTTP status (CONTRACT §7)."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message

    def body(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}


def bad(code: str, message: str) -> ApiError:
    return ApiError(400, code, message)


def unprocessable(code: str, message: str) -> ApiError:
    return ApiError(422, code, message)


def forbidden(message: str = "You are not allowed to do this.") -> ApiError:
    return ApiError(403, "FORBIDDEN", message)


def not_found(message: str = "Not found.") -> ApiError:
    return ApiError(404, "NOT_FOUND", message)


def gone(code: str, message: str) -> ApiError:
    return ApiError(410, code, message)
