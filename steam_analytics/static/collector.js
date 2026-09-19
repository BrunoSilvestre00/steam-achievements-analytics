(() => {
  const shell = document.querySelector("[data-collector]");
  if (!shell) return;
  const kind = shell.dataset.kind;
  const steamid = shell.dataset.steamid;
  const appid = shell.dataset.appid;
  const status = shell.querySelector("[data-collector-status]");
  const message = shell.querySelector("[data-collector-message]");
  const hash = window.location.hash;
  const encoded = hash.includes("=") ? hash.slice(hash.indexOf("=") + 1) : "";
  const decodePayload = () => {
    const normalized = encoded.replaceAll("-", "+").replaceAll("_", "/") + "===".slice((encoded.length + 3) % 4);
    const bytes = Uint8Array.from(atob(normalized), (char) => char.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
  };
  const listingUrl = () => {
    const url = new URL(`/profile/${steamid}`, window.location.origin);
    if (appid) url.searchParams.set("game", appid);
    return url.toString();
  };
  const finish = (text) => {
    if (status) status.textContent = text;
    if (message) message.textContent = "Coleta concluída. Abrindo sua biblioteca atualizada...";
    window.setTimeout(() => window.location.replace(listingUrl()), 700);
  };
  const fail = (text) => {
    if (status) status.textContent = "Não foi possível concluir a coleta.";
    if (message) message.textContent = `${text} Você pode fechar esta aba e tentar novamente.`;
    shell.classList.add("is-error");
  };
  (async () => {
    try {
      if (!encoded) throw new Error("O resultado da coleta não foi encontrado na URL.");
      const payload = decodePayload();
      if (kind === "trophy") {
        if (status) status.textContent = "Importando guia do PSNProfiles...";
        const response = await fetch(`/api/profile/${steamid}/games/${appid}/trophy-guide/import`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!response.ok) throw new Error("O guia não pôde ser salvo.");
        finish("Guia salvo com sucesso.");
        return;
      }
      if (kind === "steam") {
        if (status) status.textContent = "Importando jogos encontrados na Steam...";
        const response = await fetch(`/api/profile/${steamid}/steam-import`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!response.ok) throw new Error("Os jogos não puderam ser salvos.");
        finish("Biblioteca atualizada com sucesso.");
        return;
      }
      throw new Error("Tipo de coleta desconhecido.");
    } catch (error) {
      fail(error.message || "Verifique o conteúdo copiado.");
    }
  })();
})();
