# src/document_renderer_sdk/client.py
import asyncio
from typing import cast

from taskiq import AsyncResultBackend, TaskiqResult
from taskiq.kicker import AsyncKicker  # ← ИМПОРТИРУЕМ AsyncKicker
from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend
from taskiq_redis.exceptions import ResultIsMissingError

from .config import DocumentRendererSettings
from .exceptions import RenderTimeoutError, RenderError
from .schemas import RenderRequest, RenderResponse


class AsyncDocumentRendererClient:
    TASK_NAME = "src.tasks:generate_certificate_task"

    def __init__(
            self,
            settings: DocumentRendererSettings | None = None,
            broker: AioPikaBroker | None = None,
            result_backend: AsyncResultBackend | None = None,
    ):
        self.settings = settings or DocumentRendererSettings()
        self._broker = broker
        self._result_backend = result_backend
        self._is_initialized = False

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def initialize(self):
        if self._is_initialized:
            return

        if not self._broker:
            self._broker = AioPikaBroker(url=self.settings.broker_url)

        if not self._result_backend:
            self._result_backend = RedisAsyncResultBackend(
                redis_url=self.settings.result_backend_url
            )

        self._broker = self._broker.with_result_backend(self._result_backend)
        await self._broker.startup()
        self._is_initialized = True

    async def close(self):
        if self._broker and self._is_initialized:
            await self._broker.shutdown()
            await asyncio.sleep(0)  # flush pending frames
            self._is_initialized = False

    async def render_document(
            self,
            template_content: str,
            data: dict,
            filename: str | None = None,
            bucket_name: str | None = None,
            timeout: float | None = None,
    ) -> RenderResponse:
        await self.initialize()

        bucket_name = bucket_name or self.settings.s3_bucket_name

        request = RenderRequest(
            template_content=template_content,
            data=data,
            filename=filename,
            bucket_name=bucket_name,
        )

        # ✅ CORRECT: Use AsyncKicker for sending by task name
        task = await AsyncKicker(
            task_name=self.TASK_NAME,
            broker=self._broker,
            labels={},
        ).kiq(
            template_content=request.template_content,
            data=request.data,
            filename=request.filename,
            bucket_name=request.bucket_name,
        )
        task_id = task.task_id

        timeout = timeout or self.settings.default_timeout
        try:
            result = await asyncio.wait_for(
                self._poll_result(task_id),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise RenderTimeoutError(
                f"Task {task_id} did not complete within {timeout}s"
            )

        response = RenderResponse.from_task_result(result)
        if response.status == "error":
            raise RenderError(
                message=response.message or "Unknown error",
                details=response.error_details,
            )

        return response

    async def render_document_async(
            self,
            template_content: str,
            data: dict,
            filename: str | None = None,
    ) -> str:
        await self.initialize()

        # ✅ CORRECT: Use AsyncKicker
        task = await AsyncKicker(
            task_name=self.TASK_NAME,
            broker=self._broker,
            labels={},
        ).kiq(
            template_content=template_content,
            data=data,
            filename=filename,
        )
        return task.task_id

    async def get_task_result(self, task_id: str) -> RenderResponse | None:
        await self.initialize()

        # ✅ get_result returns TaskiqResult, not raw dict
        taskiq_result: TaskiqResult = await self._result_backend.get_result(task_id)
        if taskiq_result is None:
            return None

        # Extract return_value from TaskiqResult
        raw = taskiq_result.return_value
        return RenderResponse.from_task_result(raw)

    async def _poll_result(self, task_id: str) -> dict:
        while True:
            try:
                taskiq_result = await self._result_backend.get_result(task_id)
                if taskiq_result and taskiq_result.return_value:
                    return taskiq_result.return_value
                await asyncio.sleep(self.settings.poll_interval)
            except ResultIsMissingError:
                # Task is still running/pending → wait and retry
                await asyncio.sleep(self.settings.poll_interval)