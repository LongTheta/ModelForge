class InferenceError(Exception):
    """Raised when inference cannot complete; mapped to a structured HTTP error response."""

    def __init__(self, message: str, *, code: str = "inference_failed") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
