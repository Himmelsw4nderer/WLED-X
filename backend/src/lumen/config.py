from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LUMEN_", env_file=".env")

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173"]

    db_path: str = "lumen.db"

    ddp_port: int = 4048
    render_fps: int = 60

    audio_device: str | None = None
    """Substring match against a sounddevice input/monitor name. None = system default input."""
    audio_sample_rate: int = 48000
    audio_block_size: int = 1024

    hype_decay_seconds: float = 6.0


settings = Settings()
