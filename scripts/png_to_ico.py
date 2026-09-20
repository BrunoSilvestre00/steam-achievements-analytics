"""Converte a logo PNG em um ICO nativo com transparência para o Windows."""

import sys
from pathlib import Path

from PIL import Image


def convert(source: Path, destination: Path):
    with Image.open(source) as image:
        image = image.convert("RGBA")
        if image.width != image.height:
            raise ValueError("O ícone do executável precisa ser quadrado")
        image.save(destination, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: png_to_ico.py entrada.png saída.ico")
    convert(Path(sys.argv[1]), Path(sys.argv[2]))
