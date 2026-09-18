// O Python renderiza os detalhes. Este script troca o painel sem recarregar a página.
(() => {
  const panel = document.getElementById("game-detail");
  const status = document.getElementById("selection-status");
  const modal = document.getElementById("game-modal");
  if (!panel || !status || !modal) return;
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
      if (matches) visible += 1;
    });
    if (countLabel) countLabel.textContent = `${visible} encontrados`;
  }
  nameInput?.addEventListener("input", () => {
    clearTimeout(nameFilterTimer);
    nameFilterTimer = setTimeout(filterCardsByName, 500);
  });
  filterCardsByName();
  document
    .querySelector(".card-filters")
    ?.addEventListener("change", (event) => {
      if (event.target.id === "played") event.currentTarget.submit();
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
  function openModal() {
    modal.hidden = false;
    document.body.classList.add("modal-open");
    modal.querySelector(".modal-close")?.focus();
  }
  function closeModal() {
    modal.hidden = true;
    document.body.classList.remove("modal-open");
    const url = new URL(location.href);
    if (url.searchParams.has("game")) {
      url.searchParams.delete("game");
      history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
    }
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
    try {
      const response = await fetch(card.dataset.detailUrl, {
        signal: controller.signal,
      });
      if (!response.ok) throw new Error("Consulta indisponível");
      const html = await response.text();
      if (current !== sequence) return;
      panel.innerHTML = html;
      openModal();
      document.dispatchEvent(new Event("game-details-loaded"));
      hideBrokenImages(panel);
      document.querySelectorAll("a[data-game]").forEach((item) => {
        item.classList.toggle("is-selected", item === card);
        item.removeAttribute("aria-current");
      });
      card.setAttribute("aria-current", "true");
      const selectedInput = document.querySelector(
        '.card-filters input[name="game"]',
      );
      if (selectedInput) selectedInput.value = card.dataset.game;
      history.pushState({}, "", card.href);
      status.textContent = `Detalhes de ${card.querySelector("h3").textContent} carregados.`;
      panel.closest(".modal-card").scrollTop = 0;
    } catch (error) {
      if (error.name !== "AbortError" && current === sequence) {
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
