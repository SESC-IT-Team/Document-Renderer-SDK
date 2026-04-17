# src/document_renderer_sdk/client.py
import asyncio
from typing import Any
from taskiq import TaskiqMessage, AsyncResultBackend
from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend

from .config import DocumentRendererSettings
from .schemas import RenderRequest, RenderResponse
from .exceptions import RenderTimeoutError, RenderError


class AsyncDocumentRendererClient:
    """
    Async SDK client for Document-Renderer-Backend.
    Uses TaskIQ to send tasks and poll results via RabbitMQ + Redis.
    """

    TASK_NAME = "src.tasks:generate_certificate_task"  # полный путь к задаче

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
        """Инициализация брокера и бэкенда (ленивая)"""
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
        """Корректное закрытие соединений"""
        if self._broker and self._is_initialized:
            await self._broker.shutdown()
            self._is_initialized = False

    async def render_document(
        self,
        template_content: str,
        data: dict,
        filename: str | None = None,
        timeout: float | None = None,
    ) -> RenderResponse:
        """
        Отправляет задачу на рендер и ждёт результат.
        
        :param timeout: максимальное время ожидания в секундах (None = из settings)
        :raises RenderTimeoutError: если задача не выполнена за отведённое время
        :raises RenderError: если задача завершилась с ошибкой
        """
        await self.initialize()
        
        request = RenderRequest(
            template_content=template_content,
            data=data,
            filename=filename,
        )
        
        # Отправка задачи
        task = self._broker.send_task(
            self.TASK_NAME,
            template_content=request.template_content,
            data=request.data,
            filename=request.filename,
        )
        
        # Ожидание результата с таймаутом
        timeout = timeout or self.settings.default_timeout
        try:
            result = await asyncio.wait_for(
                self._poll_result(task.task_id),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise RenderTimeoutError(
                f"Task {task.task_id} did not complete within {timeout}s"
            )
        
        # Парсинг ответа
        response = RenderResponse.from_task_result(result)
        if response.status == "error":
            raise RenderError(
                message=response.message or "Unknown error",
                details=response.error_details,
            )
        
        return response

    async def _poll_result(self, task_id: str) -> dict:
        """Поллинг результата из Redis backend"""
        while True:
            result = await self._result_backend.get_result(task_id)
            if result is not None:
                # TaskIQ возвращает TaskiqResult, извлекаем return value
                return result.return_value if hasattr(result, "return_value") else result
            await asyncio.sleep(self.settings.poll_interval)

    # 🔁 Опционально: метод для fire-and-forget отправки (без ожидания)
    async def render_document_async(
        self,
        template_content: str,
        data: dict,
        filename: str | None = None,
    ) -> str:
        """
        Отправляет задачу и немедленно возвращает task_id.
        Результат можно получить позже через get_task_result(task_id).
        """
        await self.initialize()
        task = self._broker.send_task(
            self.TASK_NAME,
            template_content=template_content,
            data=data,
            filename=filename,
        )
        return task.task_id

    async def get_task_result(self, task_id: str) -> RenderResponse | None:
        """Проверяет статус задачи по task_id (не блокирует)"""
        await self.initialize()
        result = await self._result_backend.get_result(task_id)
        if result is None:
            return None
        raw = result.return_value if hasattr(result, "return_value") else result
        return RenderResponse.from_task_result(raw)