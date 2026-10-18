# Local Password browser integration — development preview

Chrome and Brave use the Chromium folder; Firefox uses its own manifest.
This preview has not been submitted to browser stores or added to release 1.31.8.
Its interface is English. "Local" here means on-device storage, not translated UI.

Click the toolbar button, then **Choose saved login**. A separate Local Password
window asks for the vault passphrase or recovery key and lets you approve one
matching account. Only that account's username and password reach the extension.
The vault stays on the computer. There is no cloud service, telemetry, browser
credential storage, local web server, automatic form submission, or background
page scanning. Every request unlocks independently; the bridge does not reuse
the desktop window's unlocked session. No vault writes are made by this preview.

If a request window is stuck or missing, reopen the popup and select **Cancel
pending request**. Native connections also expire after two minutes. Cancelling
disconnects the native port, clears the pending state, and prevents a late reply
from filling a page or interfering with a newer request.

Only exact HTTPS origins match, including nondefault ports. Subdomains are
separate sites. Save the full HTTPS website URL in each desktop entry. Archived
entries are excluded. The extension fills only the top-level page, requires one
visible password field, and refuses ambiguous username fields. Embedded login
frames, HTTP pages and multi-step sign-ins need manual copy/paste in this preview.
Websites can read values entered into their own forms, just as when you type.

## Development installation

1. On the target operating system, install the same Python/GTK/cryptography
   runtime used to build the desktop app, plus PyInstaller.
2. Run `python extensions/build.py` to create development extension folders/ZIPs.
3. Run `python extensions/build_native_host.py` to build the separate native
   host in `dist/browser-host/LocalPasswordBrowser/`. Keep that whole folder.
   The existing 1.31.8 desktop executable is GUI-only and is not a native host.
4. In Chrome or Brave, enable developer mode on the extensions page, choose
   **Load unpacked**, select `dist/extensions/chromium`, and copy its extension
   ID. Register this precise ID with the command below. Chrome and Brave may
   assign different IDs, so register each browser separately.
5. In Firefox, use `about:debugging`, **This Firefox**, **Load Temporary Add-on**,
   and select `dist/extensions/firefox/manifest.json`. Temporary loading ends on
   browser restart. The ID is `browser@localpassword.app`.
6. Register only browsers you intend to use, with an absolute host path:

```text
python extensions/register_host.py --browser chrome --extension-id YOUR_EXTENSION_ID --host ABSOLUTE_HOST_PATH
python extensions/register_host.py --browser brave --extension-id YOUR_EXTENSION_ID --host ABSOLUTE_HOST_PATH
python extensions/register_host.py --browser firefox --extension-id browser@localpassword.app --host ABSOLUTE_HOST_PATH
```

On Windows the host ends in `LocalPasswordBrowser.exe`; on Linux/macOS it is
`LocalPasswordBrowser`. Registration writes per-user browser manifests and,
on Windows, the browser's per-user native-messaging registry entry. It never
reads vault contents. Use the same command with `--remove` to unregister.
Install and register as your normal desktop user, not root. Linux sandboxed
Snap/Flatpak browsers can need additional native-messaging integration and are
not validated by this preview.

Use synthetic test entries before real accounts. Test approval/cancellation,
wrong passphrase, wrong site/subdomain/port, archived entries, navigation during
unlock, and pages with multiple or embedded login forms. Both packaged-host
and real-browser checks remain required before public distribution.

## Safari

Safari is not included in this preview. It needs a Safari Web Extension target
in a containing macOS app, its own native message handler, and integration with
the desktop vault. Reusing the Chromium host manifest does not implement Safari.
Plan its build, sandbox access and signing with the later Apple developer work.

## References

- https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging
- https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Native_messaging
- https://developer.apple.com/documentation/safariservices/messaging-between-the-app-and-javascript-in-a-safari-web-extension
