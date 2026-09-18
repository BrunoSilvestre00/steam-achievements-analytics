import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import load_env
from .steam import SteamClient, SteamError
from .storage import export_library, save_library


def main(argv=None):
    parser = argparse.ArgumentParser(description="Importa sua biblioteca Steam para SQLite, JSON e CSV.")
    parser.add_argument("command", choices=["sync"], help="Importar ou atualizar a biblioteca")
    parser.add_argument("--profile", help="SteamID64, link do perfil ou nome personalizado")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args(argv)
    try:
        load_env(args.env_file)
        client = SteamClient(os.environ.get("STEAM_API_KEY", ""))
        steamid = client.resolve_profile(args.profile or os.environ.get("STEAM_PROFILE", ""))
        games = client.owned_games(steamid)
        imported_at = datetime.now(timezone.utc).isoformat()
        database = args.data_dir / "steam.sqlite3"
        save_library(database, steamid, games, imported_at)
        print(f"Biblioteca importada: {len(games)} jogos | SteamID {steamid}")
        print(f"Banco: {database}")
        try:
            json_path, csv_path = export_library(args.data_dir, steamid, games, imported_at)
        except OSError:
            print(
                "Biblioteca salva no SQLite, mas a exportação falhou. Confira o diretório e arquivos abertos.",
                file=sys.stderr,
            )
            return 1
        print(f"JSON: {json_path}\nCSV: {csv_path}")
        known = [g["playtime_forever"] for g in games if g["playtime_forever"] is not None]
        print(f"Horas informadas pela Steam: {sum(known) / 60:.1f}")
        print(f"Jogos com zero minutos informados: {sum(minutes == 0 for minutes in known)}")
        if len(known) != len(games):
            print(f"Jogos sem tempo informado: {len(games) - len(known)}")
        return 0
    except SteamError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    except (OSError, UnicodeError, sqlite3.Error):
        print("Erro ao ler a configuração ou salvar os dados. Confira os caminhos e permissões.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
