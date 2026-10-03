class AppError(Exception):
    """Domain error mapped to an HTTP response by the API layer."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class BadRequestError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(400, detail)


class ForbiddenError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(403, detail)


class NotFoundError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(404, detail)


class ConflictError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(409, detail)
