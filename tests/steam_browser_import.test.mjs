import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

// Exercise the actual copied script without a Steam session or network access.
const source = readFileSync(new URL('../steam_analytics/static/workspace.js', import.meta.url), 'utf8');
const template = source.match(/const script = (`\(async\(\)=>\{const sid=.*`);/)[1];
const script = vm.runInNewContext(template, { steamid: '76561198339084663' });
const pages = {
  all: [{ appid: 10, name: 'Owned' }],
  perfect: [{ appid: 20, name: 'Completed' }],
  recent: [{ appid: 20, name: 'Completed' }, { appid: 30, name: 'Recent family game' }],
};
const root = (games) => ({
  querySelectorAll: () => games.map((game) => ({
    alt: game.name,
    closest: () => ({ href: `https://store.steampowered.com/app/${game.appid}/` }),
  })),
});

async function collect(active, failedTab) {
  const requested = [];
  const warnings = [];
  let result;
  await vm.runInNewContext(script, {
    URL,
    location: { href: `https://steamcommunity.com/id/example/games/?tab=${active}` },
    document: root(pages[active]),
    DOMParser: class { parseFromString(html) { return root(JSON.parse(html)); } },
    fetch: async (url, options) => {
      assert.equal(options.credentials, 'include');
      const tab = url.searchParams.get('tab');
      requested.push(tab);
      return { ok: tab !== failedTab, status: tab === failedTab ? 403 : 200, text: async () => JSON.stringify(pages[tab]) };
    },
    btoa: (value) => Buffer.from(value, 'binary').toString('base64'),
    unescape,
    console: { warn: (...args) => warnings.push(args) },
    window: { open: (url) => {
      const target = new URL(url);
      assert.equal(target.pathname, '/profile/76561198339084663/collect');
      result = JSON.parse(Buffer.from(target.hash.split('=')[1], 'base64url').toString('utf8'));
      return {};
    } },
  });
  return { ...result, requested, warnings };
}

for (const active of ['all', 'recent', 'perfect']) {
  test(`collects missing games from all three tabs when starting on ${active}`, async () => {
    const result = await collect(active);
    assert.deepEqual(result.games.map((g) => g.appid).sort((a, b) => a - b), [10, 20, 30]);
    assert.equal(result.games.find((g) => g.appid === 20).source, 'perfect');
    assert.equal(result.games.find((g) => g.appid === 30).source, 'recent');
    assert.deepEqual(result.requested.sort(), ['all', 'perfect', 'recent'].filter((tab) => tab !== active).sort());
  });
}

test('continues collecting recent games if the perfect tab fails', async () => {
  const result = await collect('all', 'perfect');
  assert.ok(result.games.some((g) => g.appid === 30));
  assert.equal(result.warnings.length, 1);
});
