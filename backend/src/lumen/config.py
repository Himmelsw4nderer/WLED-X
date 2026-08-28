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
    """Substring match against a sounddevice input/monitor name for the desktop
    loopback source. None = system default input/monitor."""
    audio_sample_rate: int = 48000
    audio_block_size: int = 1024

    audio_mic_enabled: bool = False
    """Also capture a second audio source ("mic") from a plain input device,
    alongside the desktop loopback source, so effect graphs can react to both
    at once. Off by default since not every setup has (or wants) a live mic."""
    audio_mic_device: str | None = None
    """Substring match against a sounddevice input device name for the mic
    source. None = system default input device. Only used when
    audio_mic_enabled is True."""

    hype_decay_seconds: float = 6.0

    render_enabled: bool = True
    """Set False in tests: skips starting the render loop (audio capture, background task)."""

    preview_window: bool = True
    """Open a local Tk window fed straight from the render loop -- the real
    active scene, real audio, the exact colours going to the fixtures, with no
    browser or WebSocket in the path. For eyeballing real output and render
    timing on the machine running the backend. Needs a display + tkinter; if
    either is missing it logs a warning and the backend runs on unaffected."""
    preview_window_fps: int = 30
    """How often the preview window redraws. The render loop itself always runs
    at render_fps regardless; this only throttles the local window's repaint."""


settings = Settings()
