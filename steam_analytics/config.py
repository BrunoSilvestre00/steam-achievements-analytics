import os
import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parent.parent
IS_FROZEN = bool(getattr(sys, "frozen", False))
ROOT = Path(sys.executable).resolve().parent if IS_FROZEN else SOURCE_ROOT
if IS_FROZEN:
    DATA_ROOT = Path(os.environ.get("APPDATA", ROOT)) / "Steam Achievement Analytics"
else:
    DATA_ROOT = SOURCE_ROOT / "data"
DATA_ROOT.mkdir(parents=True, exist_ok=True)


def load_env(path=ROOT / ".env"):
    """Lê pares KEY=VALUE, sem executar conteúdo nem substituir o ambiente."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or key.strip() not in ("STEAM_API_KEY", "STEAM_PROFILE"):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)
