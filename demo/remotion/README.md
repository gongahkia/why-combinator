# Remotion Demo Workspace

This workspace contains the 120-second master composition for the product demo.

## Quick start

```bash
cd demo/remotion
npm install
npm run dev
```

## Reproducible 1080p render pipeline

```bash
npm run render
```

The pipeline renders `DemoMaster` at `1920x1080`, `30fps`, `3600` frames and writes:

- `out/demo-master-1080p.mp4`
- `out/render-manifest.json`

If `public/audio/narration.wav` exists, it is injected as the narration track. Captions are always burned in using `docs/narration-sync-points.csv`.

## QA

```bash
npm run qa:render
```

The QA script validates output presence and narration sync point continuity, then writes `out/qa-report.md`. For final signoff, use [docs/qa-checklist.md](docs/qa-checklist.md).
