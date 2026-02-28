#!/usr/bin/env node

import {spawnSync} from 'node:child_process';
import {existsSync, mkdirSync, writeFileSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');
const outputDir = path.resolve(projectRoot, 'out');
const outputPath = process.env.DEMO_OUTPUT
  ? path.resolve(projectRoot, process.env.DEMO_OUTPUT)
  : path.resolve(outputDir, 'demo-master-1080p.mp4');
const syncPointsPath = path.resolve(projectRoot, 'docs/narration-sync-points.csv');
const narrationTrackRelative = process.env.NARRATION_TRACK ?? 'audio/narration.wav';
const narrationTrackAbsolute = path.resolve(projectRoot, 'public', narrationTrackRelative);

mkdirSync(outputDir, {recursive: true});
mkdirSync(path.dirname(outputPath), {recursive: true});

if (!existsSync(syncPointsPath)) {
  console.error('Missing docs/narration-sync-points.csv. Cannot run reproducible render pipeline.');
  process.exit(1);
}

const narrationTrackExists = existsSync(narrationTrackAbsolute);
const inputProps = {
  narrationTrack: narrationTrackExists ? narrationTrackRelative : null,
};

const renderArgs = [
  'remotion',
  'render',
  'src/index.ts',
  'DemoMaster',
  outputPath,
  '--codec=h264',
  '--audio-codec=aac',
  '--pixel-format=yuv420p',
  '--concurrency=4',
  '--overwrite',
  '--log=warn',
  '--props',
  JSON.stringify(inputProps),
];

const renderResult = spawnSync('npx', renderArgs, {
  cwd: projectRoot,
  stdio: 'inherit',
  env: {...process.env, FORCE_COLOR: '1'},
});

if (renderResult.status !== 0) {
  process.exit(renderResult.status ?? 1);
}

const gitRevResult = spawnSync('git', ['rev-parse', '--short', 'HEAD'], {
  cwd: projectRoot,
  encoding: 'utf8',
});
const gitRevision = gitRevResult.status === 0 ? gitRevResult.stdout.trim() : 'unknown';

const manifestPath = path.resolve(outputDir, 'render-manifest.json');
const manifest = {
  compositionId: 'DemoMaster',
  outputPath,
  generatedAt: new Date().toISOString(),
  gitRevision,
  renderSettings: {
    width: 1920,
    height: 1080,
    fps: 30,
    durationInFrames: 3600,
    codec: 'h264',
    audioCodec: 'aac',
    pixelFormat: 'yuv420p',
    concurrency: 4,
  },
  syncPointsPath,
  narrationTrack: inputProps.narrationTrack,
};

writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');

if (!narrationTrackExists) {
  console.warn(
    `Narration track not found at public/${narrationTrackRelative}. Rendered captions-only video and saved sync points in docs/narration-sync-points.csv.`,
  );
}

console.log(`Render complete: ${outputPath}`);
console.log(`Render manifest: ${manifestPath}`);
