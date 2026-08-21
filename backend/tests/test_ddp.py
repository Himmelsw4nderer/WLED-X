import struct

import numpy as np

from lumen.output import ddp


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[tuple[bytes, tuple[str, int]]] = []

    def sendto(self, data: bytes, addr: tuple[str, int]) -> None:
        self.sent.append((data, addr))

    def close(self) -> None:
        pass


def test_header_layout_small_frame():
    sock = FakeSocket()
    sender = ddp.DDPSender(sock=sock)
    pixels = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.uint8)

    sender.send_frame("10.0.0.1", pixels)

    assert len(sock.sent) == 1
    data, addr = sock.sent[0]
    assert addr == ("10.0.0.1", ddp.DDP_PORT)

    flags, seq, data_type, dest_id, offset, length = struct.unpack(">BBBBIH", data[:10])
    assert flags == (ddp.FLAG_VER1 | ddp.FLAG_PUSH)
    assert seq == 1
    assert data_type == ddp.DATA_TYPE_RGB
    assert dest_id == 0
    assert offset == 0
    assert length == 6
    assert data[10:] == bytes([1, 2, 3, 4, 5, 6])


def test_sequence_cycles_1_to_15():
    sock = FakeSocket()
    sender = ddp.DDPSender(sock=sock)
    pixels = np.zeros((1, 3), dtype=np.uint8)

    seqs = []
    for _ in range(20):
        sender.send_frame("10.0.0.1", pixels)
        seqs.append(sock.sent[-1][0][1])

    assert seqs[:15] == list(range(1, 16))
    assert seqs[15] == 1


def test_chunking_over_480_pixels():
    sock = FakeSocket()
    sender = ddp.DDPSender(sock=sock)
    pixels = np.tile(np.array([9, 9, 9], dtype=np.uint8), (500, 1))

    sender.send_frame("10.0.0.1", pixels)

    assert len(sock.sent) == 2
    first, second = (s[0] for s in sock.sent)

    f_flags, f_seq, _, _, f_offset, f_len = struct.unpack(">BBBBIH", first[:10])
    s_flags, s_seq, _, _, s_offset, s_len = struct.unpack(">BBBBIH", second[:10])

    assert f_offset == 0
    assert f_len == 480 * 3
    assert f_flags & ddp.FLAG_PUSH == 0
    assert f_flags & ddp.FLAG_VER1

    assert s_offset == 480 * 3
    assert s_len == (500 - 480) * 3
    assert s_flags & ddp.FLAG_PUSH == ddp.FLAG_PUSH
    assert f_seq == s_seq

    assert first[10:] == bytes([9, 9, 9] * 480)
    assert second[10:] == bytes([9, 9, 9] * 20)


def test_zero_led_frame_sends_single_push_packet():
    sock = FakeSocket()
    sender = ddp.DDPSender(sock=sock)
    pixels = np.zeros((0, 3), dtype=np.uint8)

    sender.send_frame("10.0.0.1", pixels)

    assert len(sock.sent) == 1
    data, _ = sock.sent[0]
    flags, _, _, _, offset, length = struct.unpack(">BBBBIH", data[:10])
    assert flags & ddp.FLAG_PUSH
    assert offset == 0
    assert length == 0
    assert data[10:] == b""


def test_module_level_send_frame_uses_default_sender(monkeypatch):
    sock = FakeSocket()
    monkeypatch.setattr(ddp, "_default_sender", ddp.DDPSender(sock=sock))

    ddp.send_frame("10.0.0.2", np.zeros((1, 3), dtype=np.uint8))

    assert len(sock.sent) == 1
    assert sock.sent[0][1] == ("10.0.0.2", ddp.DDP_PORT)
