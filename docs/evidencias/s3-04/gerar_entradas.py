"""Generate the two deterministic synthetic PPM inputs of the CPU measurement."""
from pathlib import Path
import sys

directory = Path(sys.argv[1])
directory.mkdir(parents=True, exist_ok=True)
for name, changed in [('referencia.ppm', False), ('alvo.ppm', True)]:
    pixels = bytearray()
    for y in range(256):
        for x in range(320):
            color = ((x * 3 + y * 2) % 256, (x + y) % 256, 160)
            if changed and 120 < x < 170 and 80 < y < 160:
                color = (220, 20, 20)
            pixels.extend(color)
    (directory / name).write_bytes(b'P6\n320 256\n255\n' + pixels)
