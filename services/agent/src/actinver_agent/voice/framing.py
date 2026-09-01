"""PCM framing to the avatar audio contract (docs/01-architecture/05 §3).

PCM s16le mono @ 24 kHz, ~1 s per ``agent.speak`` chunk (48 000 bytes), flushed
early at sentence boundaries so a short sentence is never delayed.
"""

from __future__ import annotations

SAMPLE_RATE_HZ = 24_000
SAMPLE_WIDTH_BYTES = 2
CHANNELS = 1
BYTES_PER_SECOND = SAMPLE_RATE_HZ * SAMPLE_WIDTH_BYTES * CHANNELS
MAX_PACKET_BYTES = 1_000_000


def chunk_bytes_for(chunk_ms: int) -> int:
    return BYTES_PER_SECOND * chunk_ms // 1000


def pcm_seconds(nbytes: int) -> float:
    return nbytes / BYTES_PER_SECOND


class PcmFramer:
    """Accumulates PCM into fixed chunks; ``flush`` returns the remainder."""

    def __init__(self, chunk_bytes: int = BYTES_PER_SECOND) -> None:
        if chunk_bytes <= 0 or chunk_bytes > MAX_PACKET_BYTES:
            raise ValueError("chunk size must be within (0, 1 MB]")
        self._chunk_bytes = chunk_bytes
        self._buffer = bytearray()

    def feed(self, pcm: bytes) -> list[bytes]:
        self._buffer.extend(pcm)
        out: list[bytes] = []
        while len(self._buffer) >= self._chunk_bytes:
            out.append(bytes(self._buffer[: self._chunk_bytes]))
            del self._buffer[: self._chunk_bytes]
        return out

    def flush(self) -> bytes | None:
        if not self._buffer:
            return None
        chunk = bytes(self._buffer)
        self._buffer.clear()
        return chunk

    def clear(self) -> None:
        self._buffer.clear()

    @property
    def pending_bytes(self) -> int:
        return len(self._buffer)


def strip_wav_header(data: bytes) -> bytes:
    """LINEAR16 responses carry a RIFF header; sent as audio it renders as a click."""
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        offset = 12
        while offset + 8 <= len(data):
            chunk_id = data[offset : offset + 4]
            size = int.from_bytes(data[offset + 4 : offset + 8], "little")
            if chunk_id == b"data":
                return data[offset + 8 : offset + 8 + size]
            offset += 8 + size + (size % 2)
    return data


def looks_like_pcm16(data: bytes) -> bool:
    """Local sanity check before a re-send (docs/01-architecture/05 §8)."""
    return bool(data) and len(data) % SAMPLE_WIDTH_BYTES == 0 and data[:4] != b"RIFF"
