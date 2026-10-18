/* Run with node --test extensions/test-background.cjs. Uses synthetic forms only. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname, 'shared/background.js'), 'utf8');

function setup({changed = false} = {}) {
  let listener, nativeCalls = 0, injections = 0;
  class Input {
    constructor(type, autocomplete = '') { this.type = type; this.autocomplete = autocomplete; this.form = null; }
    getClientRects() { return [1]; }
    dispatchEvent() {}
    set value(value) { this.filled = value; }
    get value() { return this.filled; }
  }
  const inputs = [new Input('email', 'username'), new Input('password', 'current-password')];
  const top = {};
  const context = {module: {exports: {}}, URL, Event: class {}, HTMLInputElement: Input,
    window: top, location: {origin: 'https://example.com', protocol: 'https:'},
    document: {querySelectorAll: selector => selector === 'input' ? inputs : inputs.filter(i => i.type === 'password')},
    chrome: {
      runtime: {id: 'trusted', getURL: name => 'chrome-extension://trusted/' + name,
        onMessage: {addListener: fn => { listener = fn; }},
        sendNativeMessage: async () => { nativeCalls++; return {
          ok: true, origin: 'https://example.com', username: 'synthetic-user', password: 'synthetic-password'}; }},
      tabs: {query: async () => [{id: 1, url: 'https://example.com/login'}],
        get: async () => ({url: changed ? 'https://attacker.test/login' : 'https://example.com/login'})},
      scripting: {executeScript: async request => { injections++; return [{result: true}]; }}
    }};
  top.top = top;
  vm.runInNewContext(code, context);
  return {context, Input, inputs, fill: context.module.exports.fillDocument,
    listener: (...args) => listener(...args),
    counts: () => ({nativeCalls, injections})};
}

test('only the extension popup can ask for credentials', () => {
  const fixture = setup();
  assert.equal(fixture.listener({action: 'fill'}, {id: 'trusted', tab: {id: 1},
    url: 'https://example.com'}, () => {}), false);
  assert.equal(fixture.listener({action: 'fill'}, {id: 'other',
    url: 'chrome-extension://trusted/popup.html'}, () => {}), false);
  assert.equal(fixture.counts().nativeCalls, 0);
});

test('navigation to another origin prevents credential injection', async () => {
  const fixture = setup({changed: true});
  const result = await new Promise(resolve => fixture.listener({action: 'fill'},
    {id: 'trusted', url: 'chrome-extension://trusted/popup.html'}, resolve));
  assert.equal(result.ok, false);
  assert.equal(fixture.counts().injections, 0);
});

test('field filling requires the expected HTTPS top-level origin', () => {
  const fixture = setup();
  assert.equal(fixture.fill('https://attacker.test', 'user', 'secret'), false);
  fixture.context.window.top = {};
  assert.equal(fixture.fill('https://example.com', 'user', 'secret'), false);
  assert.equal(fixture.inputs[1].filled, undefined);
});

test('multiple passwords and new-password fields are refused', () => {
  const fixture = setup();
  fixture.inputs[1].autocomplete = 'new-password';
  assert.equal(fixture.fill('https://example.com', 'user', 'secret'), false);
  fixture.inputs[1].autocomplete = 'current-password';
  fixture.inputs.push(new fixture.Input('password'));
  assert.equal(fixture.fill('https://example.com', 'user', 'secret'), false);
});

test('one unambiguous login form receives only the selected values', () => {
  const fixture = setup();
  assert.equal(fixture.fill('https://example.com', 'synthetic-user', 'synthetic-password'), true);
  assert.equal(fixture.inputs[0].filled, 'synthetic-user');
  assert.equal(fixture.inputs[1].filled, 'synthetic-password');
});
