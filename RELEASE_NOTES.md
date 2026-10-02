# Release notes

## 1.28.0

Polish release that closes the main gaps from the product plan without more Stage-by-stage drips.

### Desktop

- Skippable first-run welcome
- Light / Dark / System theme
- About section with version and privacy note
- Add password manually from Dashboard or Saved
- Default category presets (Personal, Work, Banking, Social Media, Shopping, Entertainment, Other)
- Set URL and Notes on a Saved row without Edit
- Confirm before reveal preference
- Lock vault now in Settings
- Favorites count on the Dashboard
- Clear search when a Saved filter finds nothing
- Strength line on each batch-generated password
- `SECURITY.md` documents encryption limits before public release

### Android

- URL and Notes without Edit
- Category presets in the category dialog
- Same vault helpers as desktop

### Windows apply from Stage 22

If you cannot sync the repo yet and still have Stage 22 (`password_app.py` = 212506 bytes), use the one-shot paste package:

See `uploads/APPLY_1_28.md`.

### Packaging

- Debian and Windows installer version strings set to **1.28.0**

## Still later (not required for daily use)

- Exclude user-chosen characters beyond ambiguous
- Global header search
- Sidebar icon navigation
- Breach checking
- Signed installers and monetization
- Independent security review
