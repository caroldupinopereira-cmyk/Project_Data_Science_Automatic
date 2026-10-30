const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const template = fs.readFileSync(path.join(__dirname, '../frontend/templates/dashboard.html'), 'utf8');
const nodes = new Map();
function node() {
  return {style: {}, textContent: '', innerHTML: '', children: [],
    appendChild(item) { this.children.push(item); }, scrollIntoView() {}};
}
const document = {
  getElementById(id) { if (!nodes.has(id)) nodes.set(id, node()); return nodes.get(id); },
  createElement: node,
};
const escapeHtml = value => String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const context = {document, escapeHtml};
vm.createContext(context);
const start = template.indexOf('function renderInterpretation(data)');
const end = template.indexOf('function copyText(', start);
vm.runInContext(template.slice(start, end), context);
const untrusted = '<img src=x onerror=alert(1)>';
context.renderInterpretation({summary: untrusted, conclusion: untrusted,
  key_findings: [untrusted], recommendations: [untrusted]});
assert.equal(nodes.get('interp-summary-text').textContent, untrusted);
for (const id of ['interp-findings-list', 'interp-recs-list']) {
  const html = nodes.get(id).children[0].innerHTML;
  assert.equal(html.includes('<img'), false);
  assert.equal(html.includes('&lt;img'), true);
}
console.log('PASS: interpretation renders AI output as text');

async function testPendingRequests() {
  let calls = 0;
  context.fetch = async () => {
    calls++;
    return {json: async () => ({ok: false, error: 'no_api_key', reply: 'Not configured'})};
  };
  nodes.get('interp-results').style.display = 'none';
  document.getElementById('interp-lang').value = 'id';
  const begin = template.indexOf('var _interpretationPending = false;');
  const finish = template.indexOf('function renderInterpretation(data)', begin);
  vm.runInContext(template.slice(begin, finish), context);
  context.generateInterpretation();
  context.generateInterpretation();
  assert.equal(calls, 1);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(context._interpretationPending, false);
  assert.equal(nodes.get('interp-no-key').style.display, 'block');

  context.appendChatMsg = () => ({remove() {}});
  context.datasetContext = '';
  const chatStart = template.indexOf('var _aiChatPending = false;');
  const chatEnd = template.indexOf('function escapeHtml(', chatStart);
  vm.runInContext(template.slice(chatStart, chatEnd), context);
  document.getElementById('ai-input').value = 'First';
  context.sendAIMessage();
  document.getElementById('ai-input').value = 'Second';
  context.sendAIMessage();
  assert.equal(calls, 2);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(context._aiChatPending, false);
  console.log('PASS: duplicate AI requests blocked and controls recover');
}
testPendingRequests().catch(error => { console.error(error); process.exitCode = 1; });
