import socket
import struct

import numpy as np

DDP_PORT = 4048
MAX_CHUNK_BYTES = 1440  # 480 RGB pixels per packet, DDP's practical payload cap

FLAG_VER1 = 0x40
FLAG_PUSH = 0x01
DATA_TYPE_RGB = 0x01
DEST_ID_DEFAULT = 0

_HEADER = struct.Struct(">BBBBIH")


class DDPSender:
    def __init__(self, sock: socket.socket | None = None) -> None:
        self._socket = sock or socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sequence = 0

    def close(self) -> None:
        self._socket.close()

    def send_frame(self, ip: str, pixels: np.ndarray, port: int = DDP_PORT) -> None:
        data = np.ascontiguousarray(pixels, dtype=np.uint8).reshape(-1).tobytes()
        # sequence cycles 1-15 per DDP spec (0 = unused); tracked per-sender so a
        # receiver can detect drops/reordering across successive frames.
        self._sequence = self._sequence % 15 + 1

        chunks = [data[i : i + MAX_CHUNK_BYTES] for i in range(0, len(data), MAX_CHUNK_BYTES)]
        if not chunks:
            chunks = [b""]

        last_index = len(chunks) - 1
        for index, chunk in enumerate(chunks):
            flags = FLAG_VER1 | (FLAG_PUSH if index == last_index else 0)
            offset = index * MAX_CHUNK_BYTES
            header = _HEADER.pack(
                flags, self._sequence, DATA_TYPE_RGB, DEST_ID_DEFAULT, offset, len(chunk)
            )
            self._socket.sendto(header + chunk, (ip, port))


_default_sender: DDPSender | None = None


def _sender() -> DDPSender:
    global _default_sender
    if _default_sender is None:
        _default_sender = DDPSender()
    return _default_sender


def send_frame(ip: str, pixels: np.ndarray, port: int = DDP_PORT) -> None:
    _sender().send_frame(ip, pixels, port)
