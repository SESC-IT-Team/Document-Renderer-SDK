# src/document_renderer_sdk/schemas.py
from pydantic import BaseModel, Field
from typing import Literal


class RenderRequest(BaseModel):
    template_content: str = Field(..., description="Jinja2 template string")
    data: dict = Field(default_factory=dict, description="Context data for template")
    filename: str | None = Field(default=None, description="Optional output filename")


class RenderResponse(BaseModel):
    status: Literal["success", "error"]
    filename: str | None = None
    message: str | None = None
    error_details: dict | None = None

    @classmethod
    def from_task_result(cls, result: dict) -> "RenderResponse":
        if result.get("status") == "success":
            return cls(
                status="success",
                filename=result.get("filename"),
            )
        return cls(
            status="error",
            message=result.get("message"),
            error_details=result,
        )