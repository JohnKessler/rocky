"""Image helpers with no third-party dependencies.

The Pi hands back JPEG from the ISP, so nothing here runs on the robot. It
exists so the simulator can produce real, viewable frames - which is what lets
the dashboard, the detector and the scene describer all be exercised without a
camera attached.
"""

from __future__ import annotations

import struct
import zlib


def encode_png(pixels: bytes, width: int, height: int) -> bytes:
    """Encode packed RGB bytes as a PNG."""
    if len(pixels) != width * height * 3:
        raise ValueError(f"expected {width * height * 3} bytes, got {len(pixels)}")

    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)  # filter type 0 (None) - simple and fast enough here
        raw += pixels[y * stride : (y + 1) * stride]

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + chunk(b"IEND", b"")
    )


SIGNATURE_W, SIGNATURE_H = 16, 12


def luma_signature(pixels: bytes, width: int, height: int) -> bytes:
    """Downsample packed RGB to a tiny greyscale thumbnail.

    Frames are compared through this, never through their encoded bytes -
    JPEG and PNG output changes almost completely for a trivial change in the
    image, so diffing compressed data reports motion constantly.
    """
    out = bytearray(SIGNATURE_W * SIGNATURE_H)
    if width <= 0 or height <= 0:
        return bytes(out)
    for sy in range(SIGNATURE_H):
        y = min(height - 1, sy * height // SIGNATURE_H)
        row = y * width * 3
        for sx in range(SIGNATURE_W):
            x = min(width - 1, sx * width // SIGNATURE_W)
            i = row + x * 3
            # Rec. 601 luma, integer-only
            out[sy * SIGNATURE_W + sx] = (
                pixels[i] * 77 + pixels[i + 1] * 150 + pixels[i + 2] * 29
            ) >> 8
    return bytes(out)


def frame_difference(a: bytes, b: bytes) -> float:
    """Mean absolute difference of two luma signatures, normalised to 0..1."""
    if not a or not b or len(a) != len(b):
        return 1.0
    total = sum(abs(x - y) for x, y in zip(a, b, strict=True))
    return min(1.0, (total / len(a)) / 255.0 * 4.0)
