"""Leitura pontual de metadados de guias públicos do PSNProfiles."""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


class TrophyGuideError(ValueError):
    pass


def platinum_requirements(guide, achievements):
    """Use guide tags first, then the persisted Steam online classification."""
    if guide and not guide.get("error"):
        tags = list(guide.get("tags") or [])
        for trophy in guide.get("trophies") or []:
            tags.extend(trophy.get("tags") or [])
        tags = {tag.strip().casefold() for tag in tags if tag and tag.strip()}
        has_online = any("online" in tag for tag in tags)
        has_missable = any(
            (("missable" in tag and "unmissable" not in tag) or "perdível" in tag or "perdivel" in tag) for tag in tags
        )
        return {
            "no_online": not has_online,
            "no_missable": not has_missable,
            "source": "Trophy Guide",
        }
    achievements = achievements or {}
    items = achievements.get("items") or []
    complete_data = (
        achievements.get("available")
        and len(items) == achievements.get("total")
        and bool(items)
        and all(item.get("is_online") is not None for item in items)
    )
    return {
        "no_online": bool(complete_data and not any(item["is_online"] for item in items)),
        "no_missable": False,
        "source": "Análise Steam",
    }


def trophy_count_difference(guide, achievements):
    """Compare the guide's PlayStation trophy total with Steam achievements."""
    if not guide or guide.get("error") or guide.get("trophy_count") is None:
        return None
    steam_count = (achievements or {}).get("total")
    if steam_count is None or not (achievements or {}).get("available"):
        return None
    guide_count = int(guide["trophy_count"])
    steam_count = int(steam_count)
    if guide_count == steam_count:
        return None
    difference = abs(guide_count - steam_count)
    return {
        "guide_count": guide_count,
        "steam_count": steam_count,
        "difference": difference,
        "more": "PlayStation" if guide_count > steam_count else "Steam",
        "platinum_only": guide_count == steam_count + 1,
    }


_TRANSLATION_CACHE = {}
_TAG_TRANSLATIONS = {
    "missable": "Perdível",
    "unmissable": "Imperdível",
    "buggy": "Com bugs",
    "collectable": "Colecionável",
    "collectible": "Colecionável",
    "time limited": "Tempo limitado",
    "online": "Online",
    "story": "História",
}


def _text_with_breaks(node):
    """Extract rich guide text while keeping paragraph and ``br`` breaks."""
    if node is None:
        return ""
    for br in node.find_all("br"):
        br.replace_with("\n")
    for block in node.find_all(["p", "div", "li", "h1", "h2", "h3", "h4"]):
        block.insert_before("\n")
        block.insert_after("\n")
    raw = node.get_text("", strip=False).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
    return "\n".join(line for line in lines if line)


def _translate_text(value):
    """Best-effort English to Portuguese translation with an English fallback."""
    text = (value or "").strip()
    if not text or len(text) > 4500:
        return value
    if text in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[text]
    try:
        query = urlencode({"client": "gtx", "sl": "en", "tl": "pt", "dt": "t", "q": text})
        request = Request(
            f"https://translate.googleapis.com/translate_a/single?{query}",
            headers={"User-Agent": "SteamAchievementAnalytics/1.0"},
        )
        with urlopen(request, timeout=4) as response:
            translated = json.loads(response.read().decode("utf-8"))
        result = "".join(part[0] for part in translated[0] if part and part[0])
        _TRANSLATION_CACHE[text] = result or value
        return _TRANSLATION_CACHE[text]
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        _TRANSLATION_CACHE[text] = value
        return value


def _translate_guide(data):
    texts = []
    for step in data["roadmap"]:
        texts.extend((step.get("title", ""), step.get("body", "")))
    for trophy in data["trophies"]:
        texts.extend((trophy.get("name", ""), trophy.get("description", ""), trophy.get("guide", "")))
    unique = list(dict.fromkeys(text for text in texts if text))
    with ThreadPoolExecutor(max_workers=8) as pool:
        translated = dict(zip(unique, pool.map(_translate_text, unique)))
    for step in data["roadmap"]:
        step["title_pt"] = translated.get(step.get("title", ""), step.get("title", ""))
        step["body_pt"] = translated.get(step.get("body", ""), step.get("body", ""))
    for trophy in data["trophies"]:
        trophy["name_pt"] = translated.get(trophy.get("name", ""), trophy.get("name", ""))
        trophy["description_pt"] = translated.get(trophy.get("description", ""), trophy.get("description", ""))
        trophy["guide_pt"] = translated.get(trophy.get("guide", ""), trophy.get("guide", ""))
        trophy["tags_pt"] = [_TAG_TRANSLATIONS.get(tag.casefold(), tag) for tag in trophy.get("tags", [])]
    data["tags_pt"] = [_TAG_TRANSLATIONS.get(tag.casefold(), tag) for tag in data.get("tags", [])]
    return data


def parse_trophy_guide(url, html, *, translate=False):
    parsed = urlparse(url)
    if parsed.netloc.lower() not in {"psnprofiles.com", "www.psnprofiles.com"} or not parsed.path.startswith("/guide/"):
        raise TrophyGuideError("Use uma URL de guia do PSNProfiles.")
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.stripped_strings)
    trophy_count = None
    count_node = soup.select_one(".trophy-count .small-info")
    if count_node:
        count_match = re.search(r"\d+", count_node.get_text(" ", strip=True))
        if count_match:
            trophy_count = int(count_match.group())

    overview_values = {}
    for tag in soup.select(".overview-info .tag"):
        label = tag.select_one(".typo-bottom")
        value = tag.select_one(".typo-top")
        if label and value:
            label_text = label.get_text(" ", strip=True).casefold()
            label_text = {"playthrough": "playthroughs", "hour": "hours"}.get(label_text, label_text)
            overview_values[label_text] = value.get_text(" ", strip=True)

    # The overview is authoritative. Reading the flattened page text first can
    # join the Playthroughs value with the following Hours value (for example,
    # "Playthroughs 2 Hours 20"), which incorrectly produces 20.
    def overview_number(label):
        match = re.search(r"\d+(?:\.\d+)?", overview_values.get(label, ""))
        return float(match.group()) if match else None

    difficulty = overview_number("difficulty")
    playthroughs = overview_number("playthroughs")
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
    if "hours" in overview_values:
        hours_text = overview_values["hours"]
        hours = overview_number("hours")
    # Legacy text summaries must keep each metric on its own line or row.
    # Flattening the entire document turns "1 Playthrough 100 Hours" into
    # a false "Playthrough 100" match. Never use overview text as a fallback.
    summary = BeautifulSoup(html, "html.parser")
    for overview in summary.select(".overview-info"):
        overview.decompose()
    summary_lines = []
    for node in summary.find_all(["p", "li", "tr"]):
        summary_lines.extend(node.get_text(" ", strip=True).splitlines())
    summary_lines.extend(summary.get_text("\n", strip=True).splitlines())

    def summary_number(pattern):
        for line in summary_lines:
            match = re.fullmatch(pattern, line.strip(), re.I)
            if match:
                return float(match.group(1))
        return None

    if "difficulty" not in overview_values:
        difficulty = summary_number(r"(?:estimated\s+)?difficulty\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*/\s*10[.]?")
    if "playthroughs" not in overview_values:
        playthroughs = summary_number(r"(?:minimum\s+)?playthroughs?\s*[:\-]?\s*(\d+)[.]?")
    if difficulty is None and playthroughs is None and hours is None:
        raise TrophyGuideError("Não encontrei os metadados do guia nessa página.")
    tags = []
    for tag in soup.select(".overview .tags .tag"):
        value = tag.get_text(" ", strip=True)
        if value and value not in tags:
            tags.append(value)
    roadmap = []
    for step in soup.select("#roadmapSteps [id^='roadmapStep'] .step-original"):
        title = step.find(["h1", "h2", "h3"])
        title_text = title.get_text(" ", strip=True) if title else ""
        body_source = BeautifulSoup(str(step), "html.parser")
        body_title = body_source.find(["h1", "h2", "h3"])
        if body_title:
            body_title.decompose()
        for trophy_node in body_source.select("div.trophy"):
            trophy_node.decompose()
        body = _text_with_breaks(body_source)
        if title_text or body:
            roadmap.append(
                {
                    "title": title_text,
                    "body": body,
                    "trophy_refs": [
                        node.select_one("a.title[href]").get("href")
                        for node in step.select("div.trophy")
                        if node.select_one("a.title[href]")
                    ],
                }
            )
    trophies = []
    # The `.trophy` blocks inside roadmap steps are compact references. The
    # complete achievement cards live in their own section-holder blocks.
    trophy_nodes = soup.select("div.box.section-holder")
    seen_trophies = set()
    for box in trophy_nodes:
        title = box.select_one("a.title[href*='/trophy/']") or box.select_one("a[href*='/trophy/']")
        if not title:
            continue
        trophy_key = title.get("href") or title.get_text(" ", strip=True)
        if trophy_key in seen_trophies:
            continue
        seen_trophies.add(trophy_key)
        trophy_name = title.get_text(" ", strip=True)
        row = box.select_one("table.zebra tr:nth-of-type(2)")
        description = ""
        if row:
            cells = row.find_all("td")
            if len(cells) > 1:
                description = cells[1].get_text(" ", strip=True).replace(trophy_name, "", 1).strip()
        # PSNProfiles places the guide content beside the trophy box, inside a
        # parent named SectionContainerN. Looking only inside the trophy box
        # finds the title but misses its tags and written tip.
        # In the current markup the `.trophy` element owns its own guide text.
        # Older saved pages put that text in the surrounding SectionContainer.
        local_guide = box.select(".section-original .fr-view")
        container = box.find_parent(id=re.compile(r"^SectionContainer"))
        guide_scope = box if local_guide else (container or box)
        guide_text = "\n\n".join(
            _text_with_breaks(BeautifulSoup(str(node), "html.parser"))
            for node in guide_scope.select(".section-original .fr-view")
        )
        trophy_tags = [
            tag.get_text(" ", strip=True) for tag in guide_scope.select(".section-original .section-tags .tag")
        ]
        anchor_wrapper = box.find_parent(id=re.compile(r"^[0-9]+-"))
        anchor = f"#{anchor_wrapper.get('id')}" if anchor_wrapper else title.get("href")
        trophies.append(
            {
                "name": trophy_name,
                "description": description,
                "guide": guide_text,
                "tags": trophy_tags,
                "anchor": anchor,
            }
        )
    trophy_by_anchor = {trophy.get("anchor"): trophy for trophy in trophies if trophy.get("anchor")}
    for step in roadmap:
        step["trophies"] = [trophy_by_anchor[ref] for ref in step.pop("trophy_refs", []) if ref in trophy_by_anchor]
    result = {
        "url": url,
        "difficulty": difficulty,
        "playthroughs": int(playthroughs) if playthroughs is not None else None,
        "hours": hours,
        "hours_text": hours_text,
        "trophy_count": trophy_count,
        "tags": tags,
        "roadmap": roadmap,
        "trophies": trophies,
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }
    return _translate_guide(result) if translate else result


def fetch_trophy_guide(url, *, timeout=20):
    request = Request(url, headers={"User-Agent": "SteamAnalytics/1.0 (personal project)"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return parse_trophy_guide(url, response.read(), translate=True)
    except HTTPError as error:
        if error.code == 403:
            raise TrophyGuideError(
                "O PSNProfiles bloqueou esta consulta automática (HTTP 403). Abra o guia no navegador e informe os dados manualmente."
            ) from error
        raise TrophyGuideError(f"O PSNProfiles retornou HTTP {error.code}.") from error
