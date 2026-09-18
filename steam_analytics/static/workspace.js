// O Python renderiza os detalhes. Este script troca o painel sem recarregar a página.
(() => {
  const panel = document.getElementById("game-detail");
  const status = document.getElementById("selection-status");
  const modal = document.getElementById("game-modal");
  const modalCard = modal?.querySelector(".modal-card");
  if (!panel || !status || !modal) return;
  const notice = document.querySelector(".external-notice");
  if (notice) {
    const noticeUrl = new URL(window.location.href);
    noticeUrl.searchParams.delete("notice");
    history.replaceState({}, "", `${noticeUrl.pathname}${noticeUrl.search}${noticeUrl.hash}`);
    window.setTimeout(() => notice.remove(), 10000);
  }
  function syncModalState() {
    modalCard?.classList.toggle(
      "is-complete",
      Boolean(panel.querySelector(".game-detail-content.is-complete")),
    );
  }
  function syncCardHltb(card) {
    const detail = panel.querySelector(".game-detail-content");
    if (!detail || !card) return;
    const value = detail.dataset.hltbCompletionist;
    card.dataset.hltb = value || "";
    const label = card.querySelector(".card-hltb");
    if (!label) return;
    label.textContent = value
      ? `Completionist ${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(Number(value))} h`
      : detail.dataset.hltbError === "true"
        ? "HLTB indisponível"
        : "HLTB a consultar";
  }
  let controller;
  let sequence = 0;
  function hideBrokenImages(root) {
    root.querySelectorAll("img").forEach((image) => {
      if (image.complete && image.naturalWidth === 0) image.hidden = true;
    });
  }
  document.addEventListener(
    "error",
    (event) => {
      const image = event.target;
      if (!(image instanceof HTMLImageElement)) return;
      const match = image.src.match(/steam\/apps\/(\d+)/);
      const appid = match?.[1];
      const fallbacks = appid
        ? [
            `https://cdn.akamai.steamstatic.com/steam/apps/${appid}/library_hero.jpg`,
            `https://cdn.akamai.steamstatic.com/steam/apps/${appid}/library_600x900_2x.jpg`,
          ]
        : [];
      const index = Number(image.dataset.fallbackIndex || 0);
      if (index < fallbacks.length) {
        image.dataset.fallbackIndex = String(index + 1);
        image.src = fallbacks[index];
      } else image.hidden = true;
    },
    true,
  );
  hideBrokenImages(document);
  const nameInput = document.querySelector('.card-filters input[name="q"]');
  const countLabel = document.querySelector("[data-filter-count]");
  let nameFilterTimer;
  const grid = document.querySelector(".game-grid");
  function sortCards() {
    if (!grid) return;
    const direction = grid.dataset.sort.endsWith("_desc") ? -1 : 1;
    const field = grid.dataset.sort;
    const cards = [...grid.querySelectorAll(".game-card")];
    const value = (card) =>
      field.startsWith("percent")
        ? card.dataset.percent
        : field.startsWith("hltb")
          ? card.dataset.hltb
          : field === "hours"
            ? card.dataset.hours
            : field === "recent"
              ? card.dataset.recent
              : card.dataset.gameName.toLocaleLowerCase();
    cards.sort((a, b) => {
      const av = value(a),
        bv = value(b),
        au = av === "",
        bu = bv === "";
      if (au !== bu) return au ? 1 : -1;
      if (field === "name")
        return (
          av.localeCompare(bv, "pt-BR") ||
          Number(a.dataset.nameOrder) - Number(b.dataset.nameOrder)
        );
      return (
        (Number(av) - Number(bv)) * direction ||
        Number(a.dataset.nameOrder) - Number(b.dataset.nameOrder)
      );
    });
    cards.forEach((card) => grid.append(card));
  }
  function filterCardsByName() {
    if (!nameInput) return;
    const query = nameInput.value.trim().toLocaleLowerCase();
    const cards = [...document.querySelectorAll(".game-card[data-game-name]")];
    let visible = 0;
    cards.forEach((card) => {
      const matches =
        !query || card.dataset.gameName.toLocaleLowerCase().includes(query);
      card.hidden = !matches;
      card.classList.toggle("is-filtered-out", !matches);
      if (matches) visible += 1;
    });
    if (countLabel) countLabel.textContent = `${visible} encontrados`;
  }
  function bindAchievementFilter(root) {
    const filter = root.querySelector("[data-achievement-filter]");
    if (!filter) return;
    filter.addEventListener("change", () => {
      const rows = root.querySelectorAll("[data-achievement-row]");
      rows.forEach((row) => {
        const matches =
          filter.value === "all" ||
          (filter.value === "unlocked" && row.dataset.unlocked === "true") ||
          (filter.value === "locked" && row.dataset.unlocked === "false") ||
          (filter.value === "online" && row.dataset.online === "true");
        row.hidden = !matches;
        row.classList.toggle("is-filtered-out", !matches);
      });
    });
  }
  function bindHiddenAchievements(root) {
    root.querySelectorAll("[data-achievement-reveal]").forEach((button) => {
      button.addEventListener("click", () => {
        const description = button.parentElement.querySelector(
          "[data-hidden-description]",
        );
        button.hidden = true;
        if (description) description.hidden = false;
      });
    });
  }
  function syncNameQuery() {
    if (!nameInput) return;
    const url = new URL(window.location.href);
    const query = nameInput.value.trim();
    if (query) url.searchParams.set("q", query);
    else url.searchParams.delete("q");
    window.history.replaceState(
      {},
      "",
      `${url.pathname}${url.search}${url.hash}`,
    );
  }
  nameInput?.addEventListener("input", () => {
    clearTimeout(nameFilterTimer);
    nameFilterTimer = setTimeout(() => {
      filterCardsByName();
      syncNameQuery();
    }, 500);
  });
  nameInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") event.preventDefault();
  });
  document
    .querySelector(".card-filters")
    ?.addEventListener("submit", (event) => {
      if (event.target === nameInput?.form) {
        event.preventDefault();
        clearTimeout(nameFilterTimer);
        filterCardsByName();
        syncNameQuery();
      }
    });
  filterCardsByName();
  bindAchievementFilter(panel);
  bindHiddenAchievements(panel);
  document
    .querySelector(".card-filters")
    ?.addEventListener("change", (event) => {
      if (event.target.id === "played") {
        document.querySelector('.card-filters input[name="game"]')?.remove();
        const url = new URL(window.location.href);
        url.searchParams.delete("game");
        window.history.replaceState(
          {},
          "",
          `${url.pathname}${url.search}${url.hash}`,
        );
        event.currentTarget.submit();
      }
      if (event.target.id === "sort") {
        grid.dataset.sort = event.target.value;
        sortCards();
      }
    });
  document.addEventListener("cards-progress-updated", sortCards);
  sortCards();
  document
    .querySelector("[data-hltb-update]")
    ?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = "Consultando…";
      try {
        await fetch(button.dataset.hltbUpdate, { method: "POST" });
        location.reload();
      } catch {
        button.disabled = false;
        button.textContent = "Tentar novamente";
      }
    });
  document
    .querySelector("#refresh-submit")
    ?.addEventListener("click", async () => {
      const select = document.querySelector("#refresh-mode");
      if (!select) return;
      const button = document.querySelector("#refresh-submit");
      const cancelButton = document.querySelector("#refresh-cancel");
      const form = select.form;
      const profilePath = new URL(form.action, window.location.origin).pathname;
      const steamid = profilePath.split("/")[2];
      refreshController?.abort();
      refreshController = new AbortController();
      const sync = document.querySelector("[data-progress-sync]");
      const syncTitle = sync?.querySelector("[data-progress-title]");
      const syncLabel = sync?.querySelector("[data-progress-label]");
      const syncBar = sync?.querySelector("[data-progress-sync-bar]");
      const messages = {
        all: [
          "Atualizando tudo",
          "Atualizando Steam e consultando até 5 jogos HLTB…",
        ],
        steam: [
          "Atualizando Steam",
          "Buscando sua biblioteca e progresso na Steam…",
        ],
        hltb: [
          "Atualizando HLTB",
          "Consultando at? 20 jogos sem tempo de completionist...",
        ],
        perfect: [
          "Atualizando platinas p?blicas",
          "Consultando a aba p?blica de jogos perfeitos da Steam...",
        ],
      };
      const [title, label] = messages[select.value] || messages.all;
      select.disabled = true;
      if (button) button.disabled = true;
      if (cancelButton) cancelButton.hidden = false;
      if (sync) {
        sync.hidden = false;
        sync.classList.remove("is-hidden", "is-done");
        syncTitle.textContent = title;
        syncLabel.textContent = label;
        syncBar?.removeAttribute("value");
        syncBar?.removeAttribute("max");
      }
      try {
        if (select.value === "hltb") {
          const endpoint = `/api/profile/${steamid}/hltb`;
          const initial = await fetch(endpoint, { signal: refreshController.signal });
          if (!initial.ok) throw new Error("HLTB indisponível");
          const initialData = await initial.json();
          const target = Math.min(initialData.pending, 20);
          let processed = 0;
          let pending = initialData.pending;
          if (syncBar) {
            syncBar.max = Math.max(target, 1);
            syncBar.value = 0;
          }
          while (processed < target && pending > 0) {
            const response = await fetch(`${endpoint}?limit=1`, {
              method: "POST",
              signal: refreshController.signal,
            });
            if (!response.ok) throw new Error("HLTB indisponível");
            const data = await response.json();
            if (data.pending >= pending) break;
            processed = Math.min(target, processed + pending - data.pending);
            pending = data.pending;
            if (syncBar) syncBar.value = processed;
            if (syncLabel)
              syncLabel.textContent = `${processed} de ${target} jogos HLTB processados…`;
          }
          window.location.assign(`${window.location.pathname}?updated=hltb`);
          return;
        }
        const response = await fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          redirect: "follow",
          signal: refreshController.signal,
        });
        if (!response.ok) throw new Error("Atualização indisponível");
        window.location.assign(response.url);
      } catch {
        if (refreshController.signal.aborted) {
          if (syncLabel) syncLabel.textContent = "Atualização cancelada. Os dados já salvos foram mantidos.";
          if (sync) {
            sync.classList.add("is-hidden", "is-done");
            sync.hidden = true;
          }
          document.querySelectorAll(".game-card.is-pending").forEach((card) => card.classList.remove("is-pending"));
          grid?.classList.remove("is-syncing");
          select.disabled = false;
          if (button) button.disabled = false;
          if (cancelButton) cancelButton.hidden = true;
          return;
        }
        select.disabled = false;
        if (button) button.disabled = false;
        if (syncLabel)
          syncLabel.textContent =
            "Não foi possível concluir a atualização. Tente novamente.";
      }
    });
  let refreshController;
  document.querySelector("#refresh-cancel")?.addEventListener("click", async () => {
    const select = document.querySelector("#refresh-mode");
    const button = document.querySelector("#refresh-submit");
    const cancelButton = document.querySelector("#refresh-cancel");
    const sync = document.querySelector("[data-progress-sync]");
    const form = select?.form;
    if (!select || !form) return;
    refreshController?.abort();
    const steamid = new URL(form.action, window.location.origin).pathname.split("/")[2];
    await fetch(`/api/profile/${steamid}/cancel-refresh`, { method: "POST" }).catch(() => {});
    if (sync) {
      sync.classList.add("is-hidden", "is-done");
      sync.hidden = true;
    }
    document.querySelectorAll(".game-card.is-pending").forEach((card) => card.classList.remove("is-pending"));
    grid?.classList.remove("is-syncing");
    select.disabled = false;
    if (button) button.disabled = false;
    if (cancelButton) cancelButton.hidden = true;
  });
  document.querySelector(".refresh-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
  });
  function openModal() {
    modal.hidden = false;
    document.body.classList.add("modal-open");
    modal.querySelector(".modal-close")?.focus();
  }
  function closeModal() {
    modal.hidden = true;
    document.body.classList.remove("modal-open");
    document.querySelector('.card-filters input[name="game"]')?.remove();
    const url = new URL(location.href);
    if (url.searchParams.has("game")) {
      url.searchParams.delete("game");
      history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
    }
  }
  function renderDetailSkeleton(card) {
    const appid = card.dataset.game;
    const name = card.dataset.gameName || "Jogo";
    panel.innerHTML = `
      <article class="detail-skeleton" aria-label="Carregando detalhes de ${name}">
        <div class="skeleton-art"><img src="https://cdn.akamai.steamstatic.com/steam/apps/${appid}/header.jpg" alt="" /></div>
        <div class="skeleton-body">
          <span class="skeleton-line skeleton-kicker"></span>
          <span class="skeleton-line skeleton-title"></span>
          <span class="skeleton-line skeleton-meta"></span>
          <div class="skeleton-section"><span class="skeleton-line skeleton-heading"></span><span class="skeleton-block"></span><span class="skeleton-line"></span><span class="skeleton-line short"></span></div>
          <div class="skeleton-section"><span class="skeleton-line skeleton-heading"></span><span class="skeleton-block compact"></span></div>
          <p class="detail-loading-message">Consultando conquistas e tempos deste jogo...</p>
        </div>
      </article>`;
    hideBrokenImages(panel);
  }
  function renderDetailError() {
    panel.innerHTML = '<div class="detail-loading-error"><strong>Não foi possível carregar os detalhes.</strong><span>Verifique a conexão e tente abrir o card novamente.</span></div>';
  }
  function syncSelectedCard(card) {
    document.querySelectorAll("a[data-game]").forEach((item) => {
      item.classList.toggle("is-selected", item === card);
      item.removeAttribute("aria-current");
    });
    card.setAttribute("aria-current", "true");
    const selectedInput = document.querySelector('.card-filters input[name="game"]');
    if (selectedInput) selectedInput.value = card.dataset.game;
    else {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "game";
      input.value = card.dataset.game;
      document.querySelector(".card-filters")?.prepend(input);
    }
    const modalUrl = new URL(window.location.href);
    modalUrl.searchParams.set("game", card.dataset.game);
    history.pushState({}, "", `${modalUrl.pathname}${modalUrl.search}${modalUrl.hash}`);
  }
  modal.addEventListener("click", (event) => {
    if (event.target.closest("[data-close-modal]")) closeModal();
  });
  document.addEventListener("submit", async (event) => {
    const form = event.target.closest("[data-guide-form]");
    if (!form) return;
    event.preventDefault();
    const message = form.querySelector(".guide-form-status");
    const input = form.querySelector('input[name="url"]');
    message.textContent = "Consultando guia…";
    try {
      const response = await fetch(
        `${form.dataset.guideForm}?url=${encodeURIComponent(input.value)}`,
        { method: "POST" },
      );
      const data = await response.json();
      if (!response.ok || data.error)
        throw new Error(
          data.detail || data.error || "Não foi possível consultar o guia.",
        );
      message.textContent = "Guia salvo.";
      const selectedCard = document.querySelector(
        'a[data-game][aria-current="true"]',
      );
      if (selectedCard) {
        const detailResponse = await fetch(selectedCard.dataset.detailUrl);
        if (detailResponse.ok) panel.innerHTML = await detailResponse.text();
      }
    } catch (error) {
      message.textContent = error.message;
    }
  });
  if (modal.dataset.openModal === "true") openModal();
  syncModalState();
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) closeModal();
  });
  document.addEventListener("click", async (event) => {
    const card = event.target.closest("a[data-detail-url]");
    if (
      !card ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    )
      return;
    event.preventDefault();
    controller?.abort();
    controller = new AbortController();
    const current = ++sequence;
    status.textContent = "Buscando detalhes e conquistas…";
    panel.setAttribute("aria-busy", "true");
    card.classList.add("is-pending");
    syncSelectedCard(card);
    renderDetailSkeleton(card);
    openModal();
    panel.closest(".modal-card").scrollTop = 0;
    try {
      const response = await fetch(card.dataset.detailUrl, {
        signal: controller.signal,
      });
      if (!response.ok) throw new Error("Consulta indisponível");
      const html = await response.text();
      if (current !== sequence) return;
      panel.innerHTML = html;
      syncModalState();
      syncCardHltb(card);
      bindHiddenAchievements(panel);
      bindAchievementFilter(panel);
      document.dispatchEvent(new Event("game-details-loaded"));
      hideBrokenImages(panel);
      status.textContent = `Detalhes de ${card.querySelector("h3").textContent} carregados.`;
      panel.closest(".modal-card").scrollTop = 0;
    } catch (error) {
      if (error.name !== "AbortError" && current === sequence) {
        renderDetailError();
        status.textContent =
          "Não foi possível carregar este jogo. Clique novamente para tentar.";
      }
    } finally {
      card.classList.remove("is-pending");
      if (current === sequence) panel.removeAttribute("aria-busy");
    }
  });
  window.addEventListener("popstate", () => location.reload());
})();
