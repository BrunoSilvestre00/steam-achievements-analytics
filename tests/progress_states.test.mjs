import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

test('the live card adds and removes the empty-achievements tag as data changes', () => {
  const js = readFileSync(new URL('../steam_analytics/static/progress.js', import.meta.url), 'utf8');
  const start = js.indexOf('function renderProgress(data)');
  const end = js.indexOf('async function update(', start);
  assert.ok(start >= 0 && end > start);
  const classes = new Set();
  const elements = Object.fromEntries([
    '[data-no-achievements]', '.card-progress', '[data-percent-label]',
    '[data-card-progress]', '[data-progress-count]',
  ].map((selector) => [selector, { dataset: {}, hidden: true }]));
  const card = {
    dataset: {},
    classList: { toggle: (name, enabled) => enabled ? classes.add(name) : classes.delete(name) },
    querySelector: (selector) => elements[selector],
  };
  const render = vm.runInNewContext(`(${js.slice(start, end).trim()})`, {
    cards: new Map([[1, card]]),
    renderSync: () => {},
    grid: { dataset: { sort: 'name' }, querySelectorAll: () => [] },
    document: { getElementById: () => null, dispatchEvent: () => {} },
    Event: class {},
    numbers: new Intl.NumberFormat('pt-BR'),
    status: {},
  });
  for (const [state, percent] of [['empty', null], ['ready', 0], ['pending', null], ['empty', null], ['unavailable', null]]) {
    render({ games: [{ appid: 1, state, percent, total: state === 'empty' ? 0 : 3, unlocked: 0 }], pending: 0 });
    assert.equal(classes.has('has-no-achievements'), state === 'empty');
    assert.equal(elements['[data-no-achievements]'].hidden, state !== 'empty');
    assert.equal(card.dataset.achievementsTotal, state === 'empty' ? '0' : '3');
  }
});

test('total sorting keeps zero distinct from unknown and reapplies after new data', () => {
  const js = readFileSync(new URL('../steam_analytics/static/workspace.js', import.meta.url), 'utf8');
  const start = js.indexOf('function sortCards()');
  const end = js.indexOf('function filterCardsByName()', start);
  const cards = ['', '10', '2', '0', '10'].map((total, index) => ({
    id: index,
    dataset: { achievementsTotal: total, nameOrder: index },
  }));
  let ordered = [];
  const grid = {
    dataset: { sort: 'achievements_asc' },
    querySelectorAll: () => cards,
    append: (card) => ordered.push(card.id),
  };
  const sort = vm.runInNewContext(`(${js.slice(start, end).trim()})`, { grid });
  sort();
  assert.deepEqual(ordered, [3, 2, 1, 4, 0]);
  ordered = [];
  grid.dataset.sort = 'achievements_desc';
  sort();
  assert.deepEqual(ordered, [1, 4, 2, 3, 0]);
  cards[0].dataset.achievementsTotal = '50';
  ordered = [];
  sort();
  assert.deepEqual(ordered, [0, 1, 4, 2, 3]);
});
