from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://qml:qml@localhost:5432/qml"
    containers_dir: str = "../containers"
    docker_network: str = ""
    host: str = "0.0.0.0"
    port: int = 8000
    health_poll_timeout: int = 60
    health_poll_interval: float = 1.0

    model_config = {"env_prefix": ""}


settings = Settings()
