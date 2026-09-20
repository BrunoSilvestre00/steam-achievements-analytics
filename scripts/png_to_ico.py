"""Converte um PNG quadrado em um ICO compatível com o Windows."""

import struct
import sys
from pathlib import Path


def convert(source: Path, destination: Path):
    data = source.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Arquivo não é PNG: {source}")
    width, height = struct.unpack(">II", data[16:24])
    if width != height:
        raise ValueError("O ícone do executável precisa ser quadrado")
    width_byte = 0 if width >= 256 else width
    height_byte = 0 if height >= 256 else height
    directory = struct.pack(
        "<HHHBBBBHHII",
        0,
        1,
        1,
        width_byte,
        height_byte,
        0,
        0,
        1,
        32,
        len(data),
        22,
    )
    destination.write_bytes(directory + data)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: png_to_ico.py entrada.png saída.ico")
    convert(Path(sys.argv[1]), Path(sys.argv[2]))
