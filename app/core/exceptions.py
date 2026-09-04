class ApplicationError(Exception):
    """Base class for errors safe to map at the API boundary."""


class IdempotencyConflictError(ApplicationError):
    """The request ID belongs to another user or request payload."""


class InsufficientBalanceError(ApplicationError):
    """The user does not have enough balance."""


class InvalidQuantityError(ApplicationError):
    """The requested quantity must be positive."""


class ResourceNotFoundError(ApplicationError):
    """The requested application resource was not found."""


class InvalidItemCategoryError(ApplicationError):
    """The item category is not valid for the requested operation."""


class PlacementLimitExceededError(ApplicationError):
    """The placement count would exceed the owned item quantity."""


class InvalidMemorySummaryError(ApplicationError):
    """The cat memory summary must contain non-whitespace text."""