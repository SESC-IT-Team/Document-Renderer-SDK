# src/document_renderer_sdk/exceptions.py
class DocumentRendererError(Exception):
    """Base exception for the SDK"""
    pass


class RenderTimeoutError(DocumentRendererError):
    """Raised when task execution exceeds timeout"""
    pass


class RenderError(DocumentRendererError):
    """Raised when task completes with error status"""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details