from __future__ import annotations

import math
import struct
import wave
from pathlib import Path


def tone(path: Path, sequence: list[tuple[float, float]], amplitude: float = 0.42) -> None:
    sample_rate = 44_100
    frames: list[bytes] = []
    phase = 0.0
    for frequency, duration in sequence:
        count = int(sample_rate * duration)
        for index in range(count):
            envelope = min(1.0, index / 250, (count - index) / 500)
            sample = 0.0 if frequency == 0 else amplitude * envelope * (math.sin(phase) + 0.25 * math.sin(phase * 2.01))
            frames.append(struct.pack("<h", int(max(-1, min(1, sample)) * 32767)))
            phase += 2 * math.pi * frequency / sample_rate
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(sample_rate); output.writeframes(b"".join(frames))


if __name__ == "__main__":
    root = Path("android/app/src/main/res/raw")
    tone(root / "quakemesh_warning_v1.wav", [(740, .22), (0, .08), (520, .22), (0, .08), (740, .22), (0, .08), (420, .42)])
    tone(root / "quakemesh_demo_v1.wav", [(440, .14), (0, .06), (660, .14), (0, .06), (880, .20)], amplitude=.32)
