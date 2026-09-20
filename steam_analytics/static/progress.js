// Os percentuais são calculados e persistidos pelo Python; o navegador atualiza os cards.
(() => {
  const grid = document.querySelector(".game-grid[data-progress-url]");
  const status = document.getElementById("progress-status");
  const sync = document.querySelector("[data-progress-sync]");
  const syncTitle = sync?.querySelector("[data-progress-title]");
  const syncLabel = sync?.querySelector("[data-progress-label]");
  const syncBar = sync?.querySelector("[data-progress-sync-bar]");
  if (!grid || !status) return;
  const cards = new Map(
    [...grid.querySelectorAll("[data-game]")].map((card) => [
      Number(card.dataset.game),
      card,
    ]),
  );
  const numbers = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
  let stopped = false;
  let timer;
  const controller = new AbortController();

  function renderSync(data) {
    if (!sync) return;
    const total = data.games.length;
    const pending = data.pending;
    const completed = Math.max(0, total - pending);
    const syncing = grid.dataset.syncNow === "true";
    if (!syncing) {
      sync.hidden = true;
      sync.classList.add("is-hidden");
      return;
    }
    if (!pending) {
      sync.hidden = true;
      sync.classList.add("is-hidden", "is-done");
      return;
    }
    sync.hidden = false;
    sync.classList.toggle("is-done", pending === 0);
    sync.classList.toggle("is-hidden", false);
    grid.classList.toggle("is-syncing", pending > 0);
    if (syncBar) {
      syncBar.max = Math.max(total, 1);
      syncBar.value = completed;
    }
    if (syncTitle) {
      syncTitle.textContent = pending
        ? syncing
          ? "Atualizando conquistas"
          : "Conquistas pendentes"
        : "Conquistas atualizadas";
    }
    if (syncLabel && pending && !syncing) {
      syncLabel.textContent = `${pending} jogos aguardando atualização manual`;
    } else if (syncLabel) {
      syncLabel.textContent = pending
        ? `${completed} de ${total} jogos processados · buscando conquistas…`
        : `${total} jogos processados · seus percentuais estão em dia`;
    }
    for (const game of data.games) {
      const card = cards.get(game.appid);
      if (card) card.classList.toggle("is-pending", game.needs_update);
    }
    if (!pending) {
      window.setTimeout(() => {
        if (sync && !sync.classList.contains("is-done")) return;
        sync?.classList.add("is-hidden");
        if (sync) sync.hidden = true;
      }, 1800);
    }
  }

  function renderProgress(data) {
    renderSync(data);
    for (const game of data.games) {
      const card = cards.get(game.appid);
      if (!card) continue;
      card.dataset.percent = game.percent === null ? "" : String(game.percent);
      card.dataset.achievementsTotal =
        game.total == null ? "" : String(game.total);
      card.classList.toggle("is-complete", game.percent === 100);
      const noAchievements = game.state === "empty";
      card.classList.toggle("has-no-achievements", noAchievements);
      const noAchievementsTag = card.querySelector("[data-no-achievements]");
      if (noAchievementsTag) noAchievementsTag.hidden = !noAchievements;
      const container = card.querySelector(".card-progress");
      container.dataset.progressState = game.state;
      card.querySelector("[data-percent-label]").textContent =
        game.percent !== null
          ? `${numbers.format(game.percent)}%`
          : {
              empty: "Sem conquistas",
              unavailable: "Indisponível",
              pending: "A consultar",
            }[game.state];
      const progress = card.querySelector("[data-card-progress]");
      progress.hidden = game.percent === null;
      progress.value = game.percent ?? 0;
      card.querySelector("[data-progress-count]").textContent =
        game.percent !== null
          ? `${game.unlocked}/${game.total} desbloqueadas${game.stale ? " · salvo" : ""}`
          : "—";
    }
    const completeCards = [...grid.querySelectorAll(".game-card.is-complete")];
    const totalLabel = document.getElementById("platinum-total-count");
    const recentList = document.getElementById("recent-platinums-list");
    if (totalLabel) totalLabel.textContent = completeCards.length;
    if (recentList && completeCards.length) {
      recentList.replaceChildren(
        ...completeCards.slice(0, 6).map((card) => {
          const link = document.createElement("a");
          link.href = card.querySelector(".game-card-link").href;
          link.title = card.dataset.gameName;
          const image = document.createElement("img");
          image.src = `https://cdn.akamai.steamstatic.com/steam/apps/${card.dataset.game}/library_600x900_2x.jpg`;
          image.alt = card.dataset.gameName;
          image.loading = "lazy";
          const label = document.createElement("span");
          label.textContent = card.dataset.gameName;
          link.append(image, label);
          return link;
        }),
      );
    }
    if (["percent_desc", "percent_asc"].includes(grid.dataset.sort)) {
      const direction = grid.dataset.sort === "percent_desc" ? -1 : 1;
      const ordered = [...cards.values()].sort((a, b) => {
        const aUnknown = a.dataset.percent === "";
        const bUnknown = b.dataset.percent === "";
        if (aUnknown !== bUnknown) return aUnknown ? 1 : -1;
        return (
          (Number(a.dataset.percent) - Number(b.dataset.percent)) * direction ||
          Number(a.dataset.nameOrder) - Number(b.dataset.nameOrder)
        );
      });
      ordered.forEach((card) => grid.append(card));
    }
    document.dispatchEvent(new Event("cards-progress-updated"));
    const unavailable = data.games.filter(
      (game) => game.state === "unavailable",
    ).length;
    status.textContent = data.pending
      ? `Consultando conquistas: ${data.pending} jogos restantes…`
      : `Percentuais atualizados.${unavailable ? ` ${unavailable} jogos com dados indisponíveis.` : ""}`;
  }

  async function update(method = "POST") {
    if (stopped) return;
    try {
      const response = await fetch(grid.dataset.progressUrl, {
        method,
        signal: controller.signal,
      });
      if (!response.ok) throw new Error("Consulta indisponível");
      const data = await response.json();
      if (stopped) return;
      renderProgress(data);
      if (method === "POST" && data.pending)
        timer = setTimeout(() => update(), 350);
    } catch (error) {
      if (error.name !== "AbortError") {
        status.textContent =
          "Consulta de percentuais interrompida. Os dados salvos foram mantidos; recarregue para tentar novamente.";
      }
    }
  }

  document.addEventListener("game-details-loaded", () => update("GET"));
  window.addEventListener("pagehide", () => {
    stopped = true;
    clearTimeout(timer);
    controller.abort();
  });
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) location.reload();
  });
  if (grid.dataset.skipProgress !== "true")
    update(grid.dataset.syncNow === "true" ? "POST" : "GET");
})();
