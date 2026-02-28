#!/usr/bin/env node

import {existsSync, readFileSync, statSync, writeFileSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');
const outputPath = process.env.DEMO_OUTPUT
  ? path.resolve(projectRoot, process.env.DEMO_OUTPUT)
  : path.resolve(projectRoot, 'out/demo-master-1080p.mp4');
const syncPointsPath = path.resolve(projectRoot, 'docs/narration-sync-points.csv');
const reportPath = path.resolve(projectRoot, 'out/qa-report.md');

const checks = [];

const addCheck = (passed, name, details) => {
  checks.push({passed, name, details});
};

if (existsSync(outputPath)) {
  const outputStats = statSync(outputPath);
  addCheck(outputStats.size > 0, 'Rendered MP4 exists', `${outputPath} (${outputStats.size} bytes)`);
} else {
  addCheck(false, 'Rendered MP4 exists', `${outputPath} is missing`);
}

if (!existsSync(syncPointsPath)) {
  addCheck(false, 'Narration sync points file exists', `${syncPointsPath} is missing`);
} else {
  const lines = readFileSync(syncPointsPath, 'utf8')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  const rows = lines.slice(1).map((line) => {
    const parts = line.split(',');
    return {
      segment: parts[0],
      startFrame: Number(parts[3]),
      endFrame: Number(parts[4]),
    };
  });

  addCheck(rows.length === 10, 'Sync point count', `Expected 10 segments, found ${rows.length}`);

  if (rows.length > 0) {
    addCheck(rows[0].startFrame === 0, 'Sync starts at frame 0', `start_frame=${rows[0].startFrame}`);
    addCheck(
      rows[rows.length - 1].endFrame === 3599,
      'Sync ends at frame 3599',
      `end_frame=${rows[rows.length - 1].endFrame}`,
    );
  }

  let contiguous = true;
  for (let index = 1; index < rows.length; index += 1) {
    if (rows[index].startFrame !== rows[index - 1].endFrame + 1) {
      contiguous = false;
      break;
    }
  }
  addCheck(contiguous, 'Sync frame continuity', 'Every segment starts exactly after the previous segment.');
}

const allPassed = checks.every((check) => check.passed);
const reportLines = [
  '# Render QA Report',
  '',
  `Generated: ${new Date().toISOString()}`,
  '',
  ...checks.map((check) => `- [${check.passed ? 'x' : ' '}] ${check.name}: ${check.details}`),
  '',
  allPassed ? 'Result: PASS' : 'Result: FAIL',
];

writeFileSync(reportPath, `${reportLines.join('\n')}\n`, 'utf8');
console.log(reportLines.join('\n'));
console.log(`\nSaved report: ${reportPath}`);

if (!allPassed) {
  process.exit(1);
}
