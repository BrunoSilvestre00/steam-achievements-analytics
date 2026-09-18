"""Leitura pontual de metadados de guias públicos do PSNProfiles."""

import re
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


class TrophyGuideError(ValueError):
    pass


def parse_trophy_guide(url, html):
    parsed = urlparse(url)
    if parsed.netloc.lower() not in {"psnprofiles.com", "www.psnprofiles.com"} or not parsed.path.startswith("/guide/"):
        raise TrophyGuideError("Use uma URL de guia do PSNProfiles.")
    text = " ".join(BeautifulSoup(html, "html.parser").stripped_strings)

    def number(pattern):
        match = re.search(pattern, text, re.I)
        return float(match.group(1)) if match else None

    difficulty = number(r"(?:estimated\s+)?difficulty\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*/\s*10")
    playthroughs = number(r"(?:minimum\s+)?playthroughs?\s*[:\-]?\s*(\d+)")
    hours_match = re.search(
        r"(?:approximate\s+amount\s+of\s+time\s+to\s+platinum|estimated\s+time\s+to\s+platinum|time\s+to\s+platinum)\s*[:\-]?\s*([0-9]+(?:\s*[-–]\s*[0-9]+)?)(?:\s*hours?)?",
        text,
        re.I,
    )
    hours_text = hours_match.group(1).replace(" ", "") if hours_match else None
    hours = None
    if hours_text:
        values = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", hours_text)]
        hours = sum(values) / len(values)
    if difficulty is None and playthroughs is None and hours is None:
        raise TrophyGuideError("Não encontrei os metadados do guia nessa página.")
    return {
        "url": url,
        "difficulty": difficulty,
        "playthroughs": int(playthroughs) if playthroughs is not None else None,
        "hours": hours,
        "hours_text": hours_text,
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_trophy_guide(url, *, timeout=20):
    request = Request(url, headers={"User-Agent": "SteamAnalytics/1.0 (personal project)"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return parse_trophy_guide(url, response.read())
    except HTTPError as error:
        if error.code == 403:
            raise TrophyGuideError(
                "O PSNProfiles bloqueou esta consulta automática (HTTP 403). Abra o guia no navegador e informe os dados manualmente."
            ) from error
        raise TrophyGuideError(f"O PSNProfiles retornou HTTP {error.code}.") from error
