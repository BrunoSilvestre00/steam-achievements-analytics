import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

function setup(fetch) {
  const listeners = new Map();
  const buttons = Array.from({ length: 3 }, () => ({
    dataset: { favoriteAppid: "1", favoriteUrl: "/api/profile/test/games/1/favorite" },
    attributes: { "aria-pressed": "false" },
    setAttribute(name, value) { this.attributes[name] = value; },
    getAttribute(name) { return this.attributes[name]; },
  }));
  const tag = { hidden: true };
  const card = { dataset: { favorite: "false" } };
  const feedback = {};
  const events = [];
  let observe;
  const document = {
    addEventListener: (name, callback) => listeners.set(name, callback),
    dispatchEvent: (event) => events.push(event.type),
    querySelector: (selector) => selector === "[data-favorite-feedback]" ? feedback : {},
    querySelectorAll: (selector) => selector.includes("data-favorite-appid")
      ? buttons : selector.includes("data-favorite-tag") ? [tag] : [card],
  };
  const js = readFileSync(new URL("../steam_analytics/static/favorites.js", import.meta.url), "utf8");
  vm.runInNewContext(js, {
    document, fetch, Event: class { constructor(type) { this.type = type; } },
    MutationObserver: class { constructor(callback) { observe = callback; } observe() {} },
    setTimeout: () => 1, clearTimeout: () => {},
  });
  const click = () => listeners.get("click")({
    target: { closest: () => buttons[0] }, preventDefault() {}, stopPropagation() {},
  });
  return { buttons, tag, card, feedback, events, click, observe: () => observe() };
}

test("saving and removing updates all stars, modal tag, and card together", async () => {
  const requests = [];
  const ui = setup(async (url, options) => {
    requests.push({ url, ...options });
    return { ok: true, json: async () => ({ is_favorite: JSON.parse(options.body).favorite }) };
  });
  await ui.click();
  assert.equal(requests[0].method, "PUT");
  assert.deepEqual(JSON.parse(requests[0].body), { favorite: true });
  assert.ok(ui.buttons.every((button) => button.attributes["aria-pressed"] === "true" && !button.disabled));
  assert.equal(ui.tag.hidden, false);
  assert.equal(ui.card.dataset.favorite, "true");
  ui.buttons[1].attributes["aria-pressed"] = "false";
  ui.observe();
  assert.equal(ui.buttons[1].attributes["aria-pressed"], "true");
  await ui.click();
  assert.equal(ui.tag.hidden, true);
  assert.equal(ui.card.dataset.favorite, "false");
  assert.deepEqual(ui.events, ["favorite-updated", "favorite-updated"]);
});

test("failed saves keep the previous state and enable retry", async () => {
  const ui = setup(async () => ({ ok: false }));
  await ui.click();
  assert.ok(ui.buttons.every((button) => button.attributes["aria-pressed"] === "false" && !button.disabled));
  assert.equal(ui.tag.hidden, true);
  assert.equal(ui.events.length, 0);
  assert.match(ui.feedback.textContent, /Tente novamente/);
});

test("repeated clicks while saving produce only one request", async () => {
  let finish;
  let calls = 0;
  const ui = setup(() => {
    calls += 1;
    return new Promise((resolve) => { finish = resolve; });
  });
  const first = ui.click();
  await ui.click();
  assert.equal(calls, 1);
  assert.ok(ui.buttons.every((button) => button.disabled));
  finish({ ok: true, json: async () => ({ is_favorite: true }) });
  await first;
  assert.ok(ui.buttons.every((button) => !button.disabled));
});
