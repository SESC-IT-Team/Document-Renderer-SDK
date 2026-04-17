# src/document_renderer_sdk/config.py
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import quote


class DocumentRendererSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOC_RENDERER_",
        env_file=".env",
        extra="ignore",
    )

    # RabbitMQ (TaskIQ broker)
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_vhost: str = "/"

    # Redis (result backend)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str | None = None
    redis_db: int = 0

    # Таймауты
    default_timeout: float = 300.0  # 5 минут
    poll_interval: float = 0.5      # интервал опроса результата

    @computed_field
    @property
    def broker_url(self) -> str:
        password = quote(self.rabbitmq_password) if self.rabbitmq_password else ""
        cred = f"{self.rabbitmq_user}:{password}@" if self.rabbitmq_password else f"{self.rabbitmq_user}@"
        return f"amqp://{cred}{self.rabbitmq_host}:{self.rabbitmq_port}{self.rabbitmq_vhost}"

    @computed_field
    @property
    def result_backend_url(self) -> str:
        password = f":{quote(self.redis_password)}@" if self.redis_password else ""
        return f"redis://{password}{self.redis_host}:{self.redis_port}/{self.redis_db}"