# Demo Render QA Checklist

Use this checklist after each `npm run render:demo` execution.

## 1. Pre-render inputs

- [ ] `demo/remotion/docs/narration-sync-points.csv` exists and contains 10 segments.
- [ ] Optional narration file is prepared at `demo/remotion/public/audio/narration.wav`.
- [ ] `todo.txt` task list is empty or this render is the final deliverable.

## 2. Render command

```bash
cd demo/remotion
npm ci
npm run render:demo
```

## 3. Automated QA

```bash
cd demo/remotion
npm run qa:render
```

- [ ] `out/qa-report.md` result is `PASS`.
- [ ] `out/render-manifest.json` includes expected settings: `1920x1080`, `30fps`, `3600` frames.

## 4. Manual visual/audio QA

- [ ] Video runtime is exactly `120` seconds.
- [ ] Captions are readable across all scenes and do not clip at frame edges.
- [ ] Caption timing matches `docs/narration-sync-points.csv` boundaries.
- [ ] Narration (if present) aligns to caption timing windows without drift.
- [ ] Progress bar reaches 100% at the final frame.
- [ ] No scene transition flashes, clipping artifacts, or font fallback regressions.

## 5. Final export artifact

- [ ] Output file present at `demo/remotion/out/demo-master-1080p.mp4`.
- [ ] Share `demo/remotion/out/demo-master-1080p.mp4` + `demo/remotion/out/render-manifest.json` + `demo/remotion/out/qa-report.md`.
