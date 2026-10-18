# Local Password browser preview for Windows

This is a development preview for Chrome, Brave and Firefox, not a public release.
Version 0.1.1 adds **Cancel pending request**, a two-minute request timeout, and
protection against late replies from cancelled requests. After replacing extension
files in the same folder, click Reload on the browser extensions page. This also
clears a stuck request from the older preview; no host re-registration is needed.
The native bridge reads the existing Windows vault and never modifies it. Start
with a synthetic test login and a full HTTPS website URL. Safari is not included.

1. Extract the entire ZIP into a permanent folder you control. Keep all the files
   in LocalPasswordBrowser together. Do not run the bridge executable directly.
2. Chrome: open `chrome://extensions`. Brave: open `brave://extensions`.
   Enable Developer mode, select Load unpacked, and select the **chromium** folder.
   Copy the extension's 32-letter ID.
3. Open PowerShell in the extracted folder, then register that browser:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\register-windows.ps1 -Browser chrome -ExtensionId YOUR_EXTENSION_ID
```

For Brave, replace `chrome` with `brave`, using the ID shown in Brave.

For Firefox, open `about:debugging`, select This Firefox, Load Temporary Add-on,
and choose **firefox/manifest.json**, then run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\register-windows.ps1 -Browser firefox -ExtensionId browser@localpassword.app
```

Firefox's temporary add-on is removed on browser restart. No signing-in to a
browser account or cloud service is required for this preview.

4. Open your test site's HTTPS sign-in page, click the Local Password toolbar
   icon, and choose **Choose saved login**. Enter your vault passphrase or recovery
   key only in the native Local Password window. Check the destination displayed
   there, choose the saved login, and press **Fill selected login**. The browser
   popup may close when the native window opens; this is expected. The form is
   filled after approval and is never submitted automatically.

This first version supports one top-level login form, with one visible password
field and an unambiguous username/email field. It deliberately skips embedded
frames, HTTP, multi-step logins, archived entries and ambiguous forms. Subdomains
and nondefault ports are separate destinations. Match the saved HTTPS URL exactly.

To remove integration, run the registration command with `-Remove`, then remove
the extension through the browser's extensions page. This does not delete vaults.
The bridge is not code-signed. Native Mac/Linux bridge builds and real-browser
compatibility testing still need to be completed before a public release.
