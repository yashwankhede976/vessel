# Data directory

Local filesystem storage for ingestion, split into two stages:

- `raw/` — **raw provider responses**, preserved before normalization for
  diagnosis / reprocessing. Written only when `INGESTION_SAVE_RAW=true` (opt-in).
  Layout: `raw/<source_key>/<UTC-timestamp>.json`.
- `processed/` — normalized/derived artifacts produced by the platform.

## Licensing / privacy

**This directory is git-ignored and must never be committed.** Some providers'
data is licensed or private (for example Baltic Exchange freight data is
commercial/licensed; AIS feeds and any credentials-derived data must stay
server-side). Treat everything under `raw/` as potentially licensed or private:

- Do not commit it.
- Do not redistribute licensed provider payloads.
- Do not expose raw payloads to the browser.

Keyless/open sources (Open-Meteo, World Bank, INCOIS public products,
data.gov.in open datasets) are open data but are still kept out of version
control for hygiene and size.
