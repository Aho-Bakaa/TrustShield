# TrustShield Chrome Extension

Adds a floating **"Check with TrustShield"** button to Gmail, Outlook, and
WhatsApp Web. One click sends the currently-open email/message text to the
TrustShield API and shows the verdict in the extension popup.

## Load (dev)

1. Open `chrome://extensions`
2. Enable **Developer mode** (top-right)
3. Click **Load unpacked** → select this `extension/` folder
4. Open Gmail / Outlook / WhatsApp Web — a blue button appears bottom-right

## Config

The API base URL is hardcoded to `http://127.0.0.1:8000` in `content.js` (the
dev backend). Point it at your deployed backend when ready.

## Files

- `manifest.json` — MV3 manifest, host permissions for Gmail/Outlook/WhatsApp + local API
- `content.js` — injects the button, extracts the open message, POSTs to `/api/analyze/text`
- `background.js` — stores the latest verdict for the popup
- `popup.html` / `popup.js` — shows risk level, score, and recommended action
- `make_icons.js` — regenerates placeholder icons (run `node make_icons.js`)

## Notes

- Extraction is best-effort per platform (reads visible text of the open
  message/chat). It does **not** read your full mailbox — only the currently
  open message when you click the button.
- The verdict text goes to your TrustShield backend. Use the self-hosted
  backend for privacy.
