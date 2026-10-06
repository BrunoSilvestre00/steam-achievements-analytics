"""Publish generated Markdown through the running desktop app, never its database."""

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def request_json(url, payload=None, timeout=5):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {message}") from error


def discover(base_url=None):
    if base_url:
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError("Use o endereço HTTP local da aplicação.")
        candidates = [base_url.rstrip("/")]
    else:
        candidates = [f"http://127.0.0.1:{port}" for port in range(80, 110)]
    for base in candidates:
        try:
            context = request_json(base + "/api/local/guide-context", timeout=0.5)
            if context.get("application") == "Steam Achievement Analytics":
                return base, context
        except (OSError, URLError, RuntimeError, ValueError):
            continue
    raise RuntimeError("Aplicação não encontrada. Abra o SAA atualizado; se necessário, informe --base-url.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["context", "publish"])
    parser.add_argument("--base-url")
    parser.add_argument("--appid", type=int)
    parser.add_argument("--steamid")
    parser.add_argument("--file", type=Path)
    args = parser.parse_args()
    try:
        base, context = discover(args.base_url)
        if args.action == "context":
            result = {"base_url": base, **context}
        else:
            if args.appid is None or args.appid <= 0 or args.file is None:
                raise RuntimeError("Informe --appid e --file para publicar.")
            sid = args.steamid or context.get("active_steamid")
            if not sid or not any(profile["steamid"] == sid for profile in context["profiles"]):
                raise RuntimeError("Escolha o perfil correto e informe --steamid; não foi possível inferir o destino.")
            body = args.file.read_text(encoding="utf-8-sig")
            result = request_json(f"{base}/api/profile/{sid}/games/{args.appid}/workspace/note", {"body": body})
            result["workspace_url"] = base + result["workspace_url"]
            result["file"] = str(args.file.resolve())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
