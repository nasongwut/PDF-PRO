# server/ — update channel of PDF PRO

PDF PRO checks for new versions by downloading **`latest.json`** from this folder
(default: `https://raw.githubusercontent.com/nasongwut/PDF-PRO/main/server/latest.json`,
override with the environment variable `PDFPRO_UPDATE_URL`).

* If `version` in the file is newer than the running app **and** there is a download for the
  user's platform, the app shows a banner *"PDF PRO x.y.z is available"* with **Update now**.
* If not, the app shows nothing.
* The check only happens when the user allowed it (asked once at first start, changeable in
  **••• › About PDF PRO**). Nothing is downloaded or installed without clicking **Update now**.

| file | purpose |
|---|---|
| `latest.json` | the manifest (version, notes, download URL + SHA-256 per platform, donate links) |
| `release_notes/<version>.th.md`, `.en.md` | release notes used for the manifest and the GitHub release |
| `make_manifest.py` | writes `latest.json` from the built files (run by the release workflow) |

## Releasing a new version

1. Raise `__version__` in `pdfpro/__init__.py` (e.g. `1.0.1`).
2. Add `server/release_notes/1.0.1.th.md` and `1.0.1.en.md`.
3. Commit and `git push` to `main`.

The GitHub workflow **Build & Release** then builds Windows (installer wizard) and macOS
(Apple Silicon + Intel) packages, creates the GitHub release `v1.0.1`, and updates
`latest.json` with the download links and checksums — every installed copy is notified.

## Donate links

Edit the `donate` list in `latest.json` at any time (no new release needed), e.g.

```json
"donate": [
  {"label": "GitHub Sponsors", "url": "https://github.com/sponsors/nasongwut"},
  {"label": "PromptPay / พร้อมเพย์", "url": "https://..."}
]
```

## Testing locally

```bash
python -m http.server 8000                     # in this folder
PDFPRO_UPDATE_URL=http://localhost:8000/latest.json python pdf_pro.py
```
