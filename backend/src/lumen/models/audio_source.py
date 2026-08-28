from sqlmodel import Field, SQLModel


class AudioSourceConfig(SQLModel, table=True):
    """Persisted device selection for one named audio source slot ("desktop",
    "mic"). `mode`/`device` map directly onto `AudioCapture(device, mode)`:
    mode="loopback" + device=None captures the current default output's
    monitor, mode="loopback" + an explicit "<sink>.monitor" string captures
    a specific output, and mode="input" + a device name (or None for the
    system default) captures an ordinary input like a microphone. See
    `lumen.audio.capture.discover_audio_devices` for how the UI's device
    list maps onto these two fields.

    `name` is the primary key rather than an autoincrement id because these
    are fixed slots the rest of the system refers to by name (the node
    registry's audio nodes expose a "source" param with these same names),
    not arbitrary user-created rows.
    """

    name: str = Field(primary_key=True)
    enabled: bool = True
    mode: str = "loopback"
    device: str | None = None
