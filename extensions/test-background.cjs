/* Run with node --test extensions/test-background.cjs. Uses synthetic forms only. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname, 'shared/background.js'), 'utf8');

function setup({changed = false, held = false} = {}) {
  let listener, nativeCalls = 0, injections = 0;
  const ports = [];
  const timers = new Set();
  function event() {
    const listeners = new Set();
    return {addListener: fn => listeners.add(fn), removeListener: fn => listeners.delete(fn),
      emit: value => [...listeners].forEach(fn => fn(value)), listeners};
  }
  const login = () => ({ok: true, origin: 'https://example.com',
    username: 'synthetic-user', password: 'synthetic-password'});
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
    setTimeout: fn => { timers.add(fn); return fn; }, clearTimeout: fn => timers.delete(fn),
    window: top, location: {origin: 'https://example.com', protocol: 'https:'},
    document: {querySelectorAll: selector => selector === 'input' ? inputs : inputs.filter(i => i.type === 'password')},
    chrome: {
      runtime: {id: 'trusted', getURL: name => 'chrome-extension://trusted/' + name,
        onMessage: {addListener: fn => { listener = fn; }},
        connectNative: () => {
          nativeCalls++;
          const port = {onMessage: event(), onDisconnect: event(), disconnected: false,
            disconnect() { this.disconnected = true; },
            postMessage() { if (!held) queueMicrotask(() => this.onMessage.emit(login())); }};
          ports.push(port);
          return port;
        }},
      tabs: {query: async () => [{id: 1, url: 'https://example.com/login'}],
        get: async () => ({url: changed ? 'https://attacker.test/login' : 'https://example.com/login'})},
      scripting: {executeScript: async request => { injections++; return [{result: true}]; }}
    }};
  top.top = top;
  vm.runInNewContext(code, context);
  return {context, Input, inputs, ports, login, timers, fill: context.module.exports.fillDocument,
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

const sender = {id: 'trusted', url: 'chrome-extension://trusted/popup.html'};
const send = (fixture, action) => new Promise(resolve => fixture.listener({action}, sender, resolve));
const tick = () => new Promise(resolve => setImmediate(resolve));

test('cancelling a pending request disconnects it and permits a fresh fill', async () => {
  const fixture = setup({held: true});
  const first = send(fixture, 'fill');
  await tick();
  const lateReply = [...fixture.ports[0].onMessage.listeners][0];
  assert.equal((await send(fixture, 'status')).pending, true);
  assert.equal((await send(fixture, 'fill')).error, 'busy');
  await send(fixture, 'cancel');
  assert.equal((await first).error, 'cancelled');
  assert.equal(fixture.ports[0].disconnected, true);
  assert.equal((await send(fixture, 'status')).pending, false);
  const second = send(fixture, 'fill');
  await tick();
  lateReply(fixture.login());
  await tick();
  assert.equal(fixture.counts().injections, 0);
  assert.equal((await send(fixture, 'status')).pending, true);
  fixture.ports[1].onMessage.emit(fixture.login());
  assert.equal((await second).ok, true);
  assert.equal(fixture.counts().injections, 1);
  assert.equal(fixture.timers.size, 0);
});

test('a hung host times out without filling and permits retry', async () => {
  const fixture = setup({held: true});
  const pending = send(fixture, 'fill');
  await tick();
  [...fixture.timers][0]();
  assert.equal((await pending).error, 'timed_out');
  assert.equal(fixture.counts().injections, 0);
  assert.equal(fixture.ports[0].disconnected, true);
  assert.equal((await send(fixture, 'status')).pending, false);
  const retry = send(fixture, 'fill');
  await tick();
  fixture.ports[1].onMessage.emit(fixture.login());
  assert.equal((await retry).ok, true);
});

test('closing the native host releases the request', async () => {
  const fixture = setup({held: true});
  const pending = send(fixture, 'fill');
  await tick();
  fixture.ports[0].onDisconnect.emit();
  assert.equal((await pending).ok, false);
  assert.equal((await send(fixture, 'status')).pending, false);
  assert.equal(fixture.timers.size, 0);
});

test('cancelling after approval but before tab validation prevents injection', async () => {
  const fixture = setup({held: true});
  let release;
  fixture.context.chrome.tabs.get = () => new Promise(resolve => { release = resolve; });
  const pending = send(fixture, 'fill');
  await tick();
  fixture.ports[0].onMessage.emit(fixture.login());
  await tick();
  await send(fixture, 'cancel');
  release({url: 'https://example.com/login'});
  assert.equal((await pending).error, 'cancelled');
  assert.equal(fixture.counts().injections, 0);
});

test('reopened popup exposes cancellation and unlocks the fill button afterward', async () => {
  const elements = Object.fromEntries(['fill', 'cancel', 'status', 'site'].map(id => [id, {
    hidden: id === 'cancel', disabled: false, textContent: '',
    addEventListener(name, fn) { this[name] = fn; }
  }]));
  let pending = true;
  const popup = {URL, document: {getElementById: id => elements[id]}, chrome: {
    tabs: {query: async () => [{url: 'https://example.com/login'}]},
    runtime: {sendMessage: async ({action}) => {
      if (action === 'cancel') { pending = false; return {ok: true}; }
      if (action === 'status') return {pending};
      throw new Error('Unexpected autofill');
    }}
  }};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'shared/popup.js'), 'utf8'), popup);
  await tick();
  assert.equal(elements.cancel.hidden, false);
  assert.equal(elements.fill.disabled, true);
  await elements.cancel.click();
  assert.equal(elements.cancel.hidden, true);
  assert.equal(elements.fill.disabled, false);
  assert.match(elements.status.textContent, /Cancelled/);
});
