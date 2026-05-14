# src/document_renderer_sdk/schemas.py
from pydantic import BaseModel, Field
from typing import Literal


class RenderRequest(BaseModel):
    template_content: str = Field(..., description="Jinja2 template string")
    data: dict = Field(default_factory=dict, description="Context data for template")
    filename: str | None = Field(default=None, description="Optional output filename")
    bucket_name: str | None = Field(default=None, description="Optional S3 bucket name")


class RenderResponse(BaseModel):
    status: Literal["success", "error"]
    file_url: str | None = None
    message: str | None = None
    error_details: dict | None = None

    @classmethod
    def from_task_result(cls, result: dict | None) -> "RenderResponse":
        if not result:
            return cls(
                status="error",
                message="No result from task",
            )
        if result.get("status") == "success":
            return cls(
                status="success",
                file_url=result.get("file_url"),
            )
        return cls(
            status="error",
            message=result.get("message"),
            error_details=result,
        )