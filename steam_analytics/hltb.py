"""Adaptador isolado para o wrapper comunitário do HowLongToBeat."""

from howlongtobeatpy import HowLongToBeat


class HLTBError(Exception):
    pass


class HLTBClient:
    def __init__(self, searcher=None):
        self.searcher = searcher or HowLongToBeat()

    def search(self, title):
        if not title or not title.strip():
            raise HLTBError("Título vazio.")
        try:
            results = self.searcher.search(title, similarity_case_sensitive=False)
        except Exception as error:
            raise HLTBError("HowLongToBeat recusou ou não respondeu à consulta.") from error
        if not results:
            raise HLTBError("Jogo não encontrado no HowLongToBeat.")
        best = max(results, key=lambda item: getattr(item, "similarity", -1))
        similarity = float(getattr(best, "similarity", 0) or 0)
        if similarity < 0.55:
            raise HLTBError("Nenhum resultado teve correspondência suficiente.")
        return {
            "hltb_id": int(best.game_id),
            "name": best.game_name or title,
            "similarity": round(similarity, 3),
            "main_story": best.main_story,
            "main_extra": best.main_extra,
            "completionist": best.completionist,
            "url": best.game_web_link,
        }
