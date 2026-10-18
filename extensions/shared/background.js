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

let busy = false;
api.runtime.onMessage.addListener((message, sender, respond) => {
  if (sender.id !== api.runtime.id || sender.tab || sender.url !== api.runtime.getURL("popup.html")) return false;
  if (message?.action !== "fill" || busy) { respond({ok: false, error: "busy"}); return false; }
  busy = true;
  (async () => {
    const [tab] = await api.tabs.query({active: true, currentWindow: true});
    const url = new URL(tab.url);
    if (url.protocol !== "https:" || url.username || url.password) throw new Error("https_required");
    const origin = url.origin;
    // Keep the host connection in the background when its approval window closes the popup.
    const login = await api.runtime.sendNativeMessage(HOST, {version: 1, action: "fill", origin});
    if (!login?.ok) return {ok: false, error: login?.error || "request_failed"};
    const current = await api.tabs.get(tab.id);
    if (new URL(current.url).origin !== origin || login.origin !== origin) throw new Error("site_changed");
    if (typeof login.username !== "string" || typeof login.password !== "string") throw new Error("request_failed");
    const results = await api.scripting.executeScript({
      target: {tabId: tab.id, frameIds: [0]},
      func: fillDocument, args: [origin, login.username, login.password]
    });
    login.password = "";
    return {ok: results[0]?.result === true, error: "form_not_supported"};
  })().then(respond, () => respond({ok: false, error: "connection_failed"}))
    .finally(() => { busy = false; });
  return true;
});

if (typeof module !== "undefined") module.exports = {fillDocument};
