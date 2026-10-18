const api = typeof browser === "undefined" ? chrome : browser;
const button = document.getElementById("fill");
const status = document.getElementById("status");
const cancel = document.getElementById("cancel");
let eligible = false;
let pending = false;
function showPending(value) {
  pending = value;
  button.disabled = !eligible || pending;
  cancel.hidden = !pending;
}
const errors = {
  no_matching_login: "No matching login. Save this site's full HTTPS URL in your desktop vault.",
  unlock_failed: "The vault could not be unlocked. Reopen the extension to try again.",
  cancelled: "Cancelled. Nothing was filled.",
  timed_out: "The request expired. Choose a saved login to try again.",
  form_not_supported: "This form could not be filled safely. Use the desktop app to copy your login.",
  busy: "A login request is open. Use Cancel pending request if its window is stuck."
};
api.tabs.query({active: true, currentWindow: true}).then(([tab]) => {
  const url = new URL(tab.url);
  document.getElementById("site").textContent = url.origin;
  eligible = url.protocol === "https:";
  showPending(pending);
  if (!eligible) status.textContent = "Open an HTTPS sign-in page to choose a saved login.";
}).catch(() => { button.disabled = true; });
api.runtime.sendMessage({action: "status"}).then(result => {
  showPending(result?.pending === true);
  if (pending) status.textContent = errors.busy;
}).catch(() => {});
cancel.addEventListener("click", async () => {
  await api.runtime.sendMessage({action: "cancel"});
  showPending(false);
  status.textContent = errors.cancelled;
});
button.addEventListener("click", async () => {
  showPending(true);
  status.textContent = "Continue in the Local Password window. You can reopen this popup afterward.";
  try {
    const result = await api.runtime.sendMessage({action: "fill"});
    status.textContent = result?.ok ? "Login filled. Check the page, then sign in." :
      (errors[result?.error] || "Could not connect. Check that the Local Password browser bridge is installed.");
  } catch { status.textContent = "Could not connect to Local Password."; }
  const current = await api.runtime.sendMessage({action: "status"}).catch(() => null);
  showPending(current?.pending === true);
});
