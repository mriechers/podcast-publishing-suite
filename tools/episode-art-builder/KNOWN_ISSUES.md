# Known Issues — Episode Art Builder

## Recently fixed (2026-05-07)

- **Filename field now auto-populates** with the episode slug when opened with `?episode=<slug>` (e.g., `WC_S01_13_Sharon_Blackie.jpg`). User can append `_optionA`, `_rev2`, etc. before saving. Defaults to `episode-art.jpg` when no episode is configured.
- **Per-option credits files** — `/save/credits` now derives the credits filename from the composite filename (e.g., `WC_S01_13_Sharon_Blackie_optionA.jpg` → `WC_S01_13_Sharon_Blackie_optionA_credits.md`). Previously, every save overwrote a single `credits.md`, which broke multi-option workflows.

## Preload: non-Unsplash files don't appear on initial render

**Symptom:** When opened with `?episode=<slug>`, files in `episode-preload/manifest.json` that are NOT Unsplash format (e.g., guest portraits like `Sharon Blackie photo.JPG`) don't appear in the source pool until the user switches to another tab (e.g., Unsplash Search) and switches back. Once the tab switch fires, the file appears "like an upload" — meaning the upload-handling code path renders it, not the preload code path.

**Repro:** Run `/wc-episode-art` for an episode whose `Images/` folder contains a guest portrait + Unsplash thematics. Open the builder. Unsplash files appear immediately with credits attached. The portrait does not appear. Switch tabs, switch back — portrait appears.

**Likely cause:** The preload code path for non-Unsplash files is gated on a credit form being filled out, but the form's render is tied to a tab/state change rather than firing on initial load. Need to inspect the JS in `public/index.html` (or whatever the entry is) to confirm.

**Workaround:** Switch to Unsplash Search tab, switch back to Upload Images / source pool. Portrait will appear.

**Found:** 2026-05-07, during E13 Sharon Blackie art build.
