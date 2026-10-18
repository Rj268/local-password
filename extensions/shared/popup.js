const api = typeof browser === "undefined" ? chrome : browser;
const button = document.getElementById("fill");
const status = document.getElementById("status");
const errors = {
  no_matching_login: "No matching login. Save this site's full HTTPS URL in your desktop vault.",
  unlock_failed: "The vault could not be unlocked. Reopen the extension to try again.",
  cancelled: "Cancelled. Nothing was filled.",
  form_not_supported: "This form could not be filled safely. Use the desktop app to copy your login.",
  busy: "A login request is already open in Local Password."
};
api.tabs.query({active: true, currentWindow: true}).then(([tab]) => {
  const url = new URL(tab.url);
  document.getElementById("site").textContent = url.origin;
  button.disabled = url.protocol !== "https:";
  if (button.disabled) status.textContent = "Open an HTTPS sign-in page to choose a saved login.";
}).catch(() => { button.disabled = true; });
button.addEventListener("click", async () => {
  button.disabled = true;
  status.textContent = "Continue in the Local Password window. You can reopen this popup afterward.";
  try {
    const result = await api.runtime.sendMessage({action: "fill"});
    status.textContent = result?.ok ? "Login filled. Check the page, then sign in." :
      (errors[result?.error] || "Could not connect. Check that the Local Password browser bridge is installed.");
  } catch { status.textContent = "Could not connect to Local Password."; }
  button.disabled = false;
});
