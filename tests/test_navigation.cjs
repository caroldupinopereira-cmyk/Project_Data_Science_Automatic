const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function element(id) {
  const classes = new Set();
  return { id, style: {}, classList: {
    add: value => classes.add(value), remove: value => classes.delete(value),
    contains: value => classes.has(value),
  }};
}
const ids = {};
for (const id of ['tab-overview', 'tab-numerical', 'tab-visualizations', 'tab-timeseries',
  'tab-interpretation', 'menu-overview', 'menu-numerical', 'menu-visualizations',
  'menu-timeseries', 'menu-interpretation', 'acc-stats', 'acc-viz', 'acc-ts']) {
  ids[id] = element(id);
}
for (const id of ['acc-stats', 'acc-viz', 'acc-ts']) ids[id].previousElementSibling = element(id + '-btn');
const document = {
  getElementById: id => ids[id] || null,
  querySelectorAll: selector => Object.values(ids).filter(el =>
    selector === '.tab-content' ? el.id.startsWith('tab-') : el.id.startsWith('menu-')),
  querySelector: () => null,
};
const source = fs.readFileSync(path.join(__dirname, '../frontend/static/js/script.js'), 'utf8');
const context = { document, setTimeout: fn => fn() };
vm.createContext(context);
// Load the real tab-switching function without the page initialization hooks.
vm.runInContext(source.slice(0, source.indexOf('/* ─── DARK MODE')), context);
for (const [tab, accordion] of [['numerical', 'acc-stats'], ['visualizations', 'acc-viz'], ['timeseries', 'acc-ts']]) {
  context.switchTab(tab);
  assert.equal(ids['tab-' + tab].style.display, 'block');
  assert.equal(ids[accordion].classList.contains('open'), true);
  assert.equal(ids['menu-' + tab].classList.contains('active'), true);
}
context.switchTab('interpretation');
assert.equal(ids['menu-interpretation'].classList.contains('active'), true);
context.switchTab('missing-tab');
assert.equal(ids['tab-interpretation'].style.display, 'block');
console.log('PASS: tab selection, three accordions, interpretation menu, unknown tab');
