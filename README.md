# podcast-publishing-suite

A meta-repository for an agentic podcast publishing pipeline. Each service handles a stage in the workflow — from transcription and pre-production through web publishing to social distribution.

## Pipeline

```
Audio File
  │
  ├─→ modules/podcast-whisper-transcription  (transcribe + diarize)
  │
  ├─→ modules/prx-to-ghost-publisher        (PRX feed → Ghost CMS)
  │
  ├─→ modules/audiogram-tools               (video audiograms)
  │
  ├─→ modules/robo-social                   (social distribution)
  │
  └─→ frontend/                              (unified dashboard)

```

## Modules

| Module | Description |
|--------|-------------|
| [podcast-whisper-transcription](modules/podcast-whisper-transcription/) | Transcription pipeline using OpenAI Whisper |
| [prx-to-ghost-publisher](modules/prx-to-ghost-publisher/) | Automated PRX podcast feed → Ghost CMS publisher |
| [audiogram-tools](modules/audiogram-tools/) | Animated audiogram generation from podcast audio |

## Frontend

The `frontend/` directory contains a unified dashboard built with React 18 + Vite + Tailwind (web UI) and FastAPI (API backend). See [frontend/README.md](frontend/README.md) for setup instructions.

## Shows

Per-show configuration lives in `shows/`. Each show has a `config.json` with PRX feed URLs, Ghost CMS targets, and branding info.

| Show | Config |
|------|--------|

## Reference

The `reference/` directory (gitignored) contains archived planning docs and earlier project iterations — including the original podbridge editorial assistant and the cardigan-dashboard-template that `frontend/` was bootstrapped from.

## Getting Started


## Individual Projects

Each submodule has its own README with setup instructions. See the links in the Modules table above.
