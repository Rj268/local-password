/* No persistent credentials, network calls, or website message listeners. */
const api = typeof browser === "undefined" ? chrome : browser;
const HOST = "app.localpassword.browser";

function fillDocument(origin, username, password) {
  if (window.top !== window || location.origin !== origin || location.protocol !== "https:") return false;
  const visible = el => !el.disabled && !el.readOnly && el.getClientRects().length > 0;
  const passwords = [...document.querySelectorAll('input[type="password"]')].filter(visible);
  // Ambiguous forms and password-change pages require manual entry.
  if (passwords.length !== 1 || passwords[0].autocomplete === "new-password") return false;
  const passwordInput = passwords[0];
  const scope = passwordInput.form || document;
  const usernames = [...scope.querySelectorAll('input')].filter(el =>
    visible(el) && ["text", "email"].includes(el.type) &&
    !["one-time-code", "new-password"].includes(el.autocomplete));
  const marked = usernames.filter(el => el.autocomplete === "username");
  const usernameInput = marked.length === 1 ? marked[0] : (usernames.length === 1 ? usernames[0] : null);
  if (username && !usernameInput) return false;
  const setValue = (el, value) => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, value);
    el.dispatchEvent(new Event("input", {bubbles: true}));
    el.dispatchEvent(new Event("change", {bubbles: true}));
  };
  if (usernameInput && username) setValue(usernameInput, username);
  setValue(passwordInput, password);
  return true;
}

let activeRequest = null;
const REQUEST_TIMEOUT_MS = 120000;

function nativeLogin(request, origin) {
  return new Promise(resolve => {
    let port;
    let settled = false;
    const finish = result => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (port) {
        port.onMessage.removeListener(onMessage);
        port.onDisconnect.removeListener(onDisconnect);
        try { port.disconnect(); } catch {}
      }
      resolve(result);
    };
    const onMessage = result => finish(result);
    const onDisconnect = () => {
      // Read lastError here so an expected closed host does not leave an unchecked error.
      const lastError = api.runtime.lastError;
      finish({ok: false, error: lastError ? "connection_failed" : "cancelled"});
    };
    const timer = setTimeout(() => {
      request.cancelled = true;
      if (activeRequest === request) activeRequest = null;
      finish({ok: false, error: "timed_out"});
    }, REQUEST_TIMEOUT_MS);
    request.abort = () => finish({ok: false, error: "cancelled"});
    try {
      port = api.runtime.connectNative(HOST);
      port.onMessage.addListener(onMessage);
      port.onDisconnect.addListener(onDisconnect);
      port.postMessage({version: 1, action: "fill", origin});
    } catch { finish({ok: false, error: "connection_failed"}); }
  });
}

api.runtime.onMessage.addListener((message, sender, respond) => {
  if (sender.id !== api.runtime.id || sender.tab || sender.url !== api.runtime.getURL("popup.html")) return false;
  if (message?.action === "status") { respond({pending: activeRequest !== null}); return false; }
  if (message?.action === "cancel") {
    const request = activeRequest;
    activeRequest = null;
    if (request) {
      request.cancelled = true;
      request.abort?.();
    }
    respond({ok: true});
    return false;
  }
  if (message?.action !== "fill") return false;
  if (activeRequest) { respond({ok: false, error: "busy"}); return false; }
  const request = {cancelled: false, abort: null};
  activeRequest = request;
  const isCurrent = () => !request.cancelled && activeRequest === request;
  const reply = result => { try { respond(result); } catch {} };
  (async () => {
    const [tab] = await api.tabs.query({active: true, currentWindow: true});
    if (!isCurrent()) return {ok: false, error: "cancelled"};
    const url = new URL(tab.url);
    if (url.protocol !== "https:" || url.username || url.password) throw new Error("https_required");
    const origin = url.origin;
    // Keep the host connection in the background when its approval window closes the popup.
    const login = await nativeLogin(request, origin);
    if (!isCurrent()) return {ok: false, error: login?.error || "cancelled"};
    if (!login?.ok) return {ok: false, error: login?.error || "request_failed"};
    const current = await api.tabs.get(tab.id);
    if (!isCurrent()) { login.password = ""; return {ok: false, error: "cancelled"}; }
    if (new URL(current.url).origin !== origin || login.origin !== origin) throw new Error("site_changed");
    if (typeof login.username !== "string" || typeof login.password !== "string") throw new Error("request_failed");
    const results = await api.scripting.executeScript({
      target: {tabId: tab.id, frameIds: [0]},
      func: fillDocument, args: [origin, login.username, login.password]
    });
    login.password = "";
    return {ok: results[0]?.result === true, error: "form_not_supported"};
  })().then(result => {
    if (activeRequest === request) activeRequest = null;
    reply(result);
  }, () => {
    if (activeRequest === request) activeRequest = null;
    reply({ok: false, error: "connection_failed"});
  });
  return true;
});

if (typeof module !== "undefined") module.exports = {fillDocument};
