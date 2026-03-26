from textx import get_location
from textx.exceptions import TextXSemanticError


class ValidationError(TextXSemanticError):
    def __init__(self, message, obj):
        location = get_location(obj)
        self.line = location.get("line")
        self.col = location.get("col")
        self.filename = location.get("filename")
        super().__init__(message, **location)


class MissingRequiredValueError(ValidationError):
    pass


class InvalidRangeError(ValidationError):
    pass


class InvalidEnumError(ValidationError):
    pass


class InvalidGenerateCountError(ValidationError):
    pass


class InvalidPrecisionError(ValidationError):
    pass


class InvalidIncludeFieldError(ValidationError):
    pass


class InvalidIncludeValueError(ValidationError):
    pass


class InvalidPartitionsError(ValidationError):
    pass


class InvalidReferenceError(ValidationError):
    pass