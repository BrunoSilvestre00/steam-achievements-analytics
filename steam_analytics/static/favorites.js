(() => {
  const pending = new Set();
  const saved = new Map();
  let feedbackTimer;

  function syncFavorite(appid, favorite) {
    document
      .querySelectorAll(`[data-favorite-appid="${appid}"]`)
      .forEach((button) => {
        const label = favorite
          ? "Remover dos favoritos"
          : "Adicionar aos favoritos";
        button.setAttribute("aria-pressed", String(favorite));
        button.setAttribute("aria-label", label);
        button.title = label;
        button.disabled = pending.has(appid);
      });
    document
      .querySelectorAll(`[data-favorite-tag="${appid}"]`)
      .forEach((tag) => {
        tag.hidden = !favorite;
      });
    document
      .querySelectorAll(`.game-card[data-game="${appid}"]`)
      .forEach((card) => {
        card.dataset.favorite = String(favorite);
      });
  }

  function showFeedback(message) {
    let feedback = document.querySelector("[data-favorite-feedback]");
    if (!feedback) {
      feedback = document.createElement("div");
      feedback.dataset.favoriteFeedback = "";
      feedback.className = "favorite-feedback";
      feedback.setAttribute("role", "status");
      document.body.append(feedback);
    }
    feedback.textContent = message;
    feedback.hidden = false;
    clearTimeout(feedbackTimer);
    feedbackTimer = setTimeout(() => {
      feedback.hidden = true;
    }, 5000);
  }

  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-favorite-button]");
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();
    const appid = button.dataset.favoriteAppid;
    if (pending.has(appid)) return;
    const favorite = button.getAttribute("aria-pressed") !== "true";
    pending.add(appid);
    syncFavorite(appid, !favorite);
    try {
      const response = await fetch(button.dataset.favoriteUrl, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ favorite }),
      });
      if (!response.ok) throw new Error("Falha ao salvar favorito");
      const data = await response.json();
      if (typeof data.is_favorite !== "boolean")
        throw new Error("Resposta inválida");
      saved.set(appid, data.is_favorite);
      syncFavorite(appid, data.is_favorite);
      document.dispatchEvent(new Event("favorite-updated"));
      showFeedback(
        data.is_favorite
          ? "Jogo adicionado aos favoritos."
          : "Jogo removido dos favoritos.",
      );
    } catch {
      showFeedback("Não foi possível salvar o favorito. Tente novamente.");
    } finally {
      pending.delete(appid);
      syncFavorite(appid, saved.get(appid) ?? !favorite);
    }
  });

  // A modal request started before a save can return an outdated star.
  // Reapply successful changes when detail content is inserted or replaced.
  const observer = new MutationObserver(() => {
    saved.forEach((favorite, appid) => syncFavorite(appid, favorite));
  });
  const panel = document.querySelector("#game-detail");
  if (panel) observer.observe(panel, { childList: true, subtree: true });
  document.addEventListener("game-details-loaded", () => {
    saved.forEach((favorite, appid) => syncFavorite(appid, favorite));
  });
})();
