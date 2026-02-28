import React from 'react';
import {AbsoluteFill, Sequence, interpolate, useCurrentFrame} from 'remotion';

import {ApiPayloadCard} from '../components/ApiPayloadCard';
import {MetricTile} from '../components/MetricTile';
import {SceneLayout} from '../components/SceneLayout';
import {SceneTransition} from '../components/SceneTransition';
import {fontStack, palette} from '../theme';

const SCENE_LENGTH = 360;

const scenes = [
  {id: 'intro', from: 0},
  {id: 'challenge', from: 360},
  {id: 'run', from: 720},
  {id: 'execution', from: 1080},
  {id: 'judging', from: 1440},
  {id: 'scoring', from: 1800},
  {id: 'replay', from: 2160},
  {id: 'leaderboard', from: 2520},
  {id: 'artifacts', from: 2880},
  {id: 'outro', from: 3240},
] as const;

const challengePayload = `{
  "title": "AI Incident Triage",
  "risk_appetite": "balanced",
  "complexity_slider": 0.5,
  "iteration_window_seconds": 1800,
  "minimum_quality_threshold": 0.2
}`;

const runStartPayload = `{
  "id": "run_8f3d...",
  "state": "running",
  "reproducibility": {
    "seed_algorithm": "sha256-uuid5-v1",
    "run_seed": 1842309912
  }
}`;

const scoringPayload = `{
  "components": {
    "quality": 0.82,
    "novelty": 0.77,
    "feasibility": 0.74,
    "criteria": 0.79,
    "similarity_penalty": 0.18,
    "too_safe_penalty": 0.05
  },
  "novelty_strategy_mode": "hybrid_overlap"
}`;

const replayPayload = `{
  "checkpoint_id": "checkpoint:20260228T001200Z",
  "delta_summary": {
    "submission_12": -0.012,
    "submission_27": 0.000,
    "submission_31": 0.009
  }
}`;

const LeaderboardRows: React.FC<{highlight: number}> = ({highlight}) => {
  const rows = [
    {rank: 1, team: 'Red', score: '0.911', delta: '+0.013'},
    {rank: 2, team: 'Blue', score: '0.896', delta: '+0.004'},
    {rank: 3, team: 'Green', score: '0.882', delta: '-0.002'},
    {rank: 4, team: 'Orange', score: '0.871', delta: '+0.006'},
  ];

  return (
    <div
      style={{
        width: 900,
        backgroundColor: '#fffdfa',
        border: `2px solid ${palette.accentSoft}`,
        borderRadius: 18,
        overflow: 'hidden',
        boxShadow: `0 12px 24px ${palette.shadow}`,
      }}
    >
      <div style={{display: 'grid', gridTemplateColumns: '100px 1fr 220px 180px', padding: '12px 18px', fontFamily: fontStack.mono, fontSize: 16, letterSpacing: 1.1, textTransform: 'uppercase', backgroundColor: '#f9efe6'}}>
        <span>Rank</span>
        <span>Team</span>
        <span>Score</span>
        <span>Delta</span>
      </div>
      {rows.map((row, index) => (
        <div
          key={row.rank}
          style={{
            display: 'grid',
            gridTemplateColumns: '100px 1fr 220px 180px',
            padding: '14px 18px',
            fontSize: 30,
            backgroundColor: index === highlight ? '#fff1e7' : '#fffdfa',
            borderTop: '1px solid #f1e4d7',
          }}
        >
          <span style={{fontFamily: fontStack.display}}>{row.rank}</span>
          <span>{row.team}</span>
          <span style={{fontFamily: fontStack.mono}}>{row.score}</span>
          <span style={{color: row.delta.startsWith('-') ? '#b15339' : palette.success, fontFamily: fontStack.mono}}>{row.delta}</span>
        </div>
      ))}
    </div>
  );
};

const ProgressRail: React.FC = () => {
  const frame = useCurrentFrame();
  const stages = [
    {label: 'Planner', at: 60},
    {label: 'Hacker', at: 110},
    {label: 'Subagents', at: 170},
    {label: 'Validators', at: 230},
    {label: 'Scoring', at: 300},
  ];

  return (
    <div style={{display: 'grid', gap: 16, width: 960}}>
      {stages.map((stage) => {
        const fill = Math.max(0, Math.min(1, (frame - stage.at) / 45));
        return (
          <div key={stage.label} style={{display: 'grid', gridTemplateColumns: '220px 1fr', alignItems: 'center', gap: 20}}>
            <div style={{fontFamily: fontStack.mono, fontSize: 22}}>{stage.label}</div>
            <div style={{height: 18, backgroundColor: '#efdccc', borderRadius: 999, overflow: 'hidden'}}>
              <div style={{width: `${fill * 100}%`, height: '100%', backgroundColor: palette.accent, transition: 'width 80ms linear'}} />
            </div>
          </div>
        );
      })}
    </div>
  );
};

export const MasterComposition: React.FC = () => {
  return (
    <AbsoluteFill>
      <Sequence from={scenes[0].from} durationInFrames={SCENE_LENGTH}>
        <SceneTransition>
          <SceneLayout
            eyebrow="Hackathon Service"
            title="Autonomous Build-to-Judge Pipeline"
            subtitle="2-minute product walkthrough"
            footer="Challenge setup -> run start -> execution -> judging -> scoring -> leaderboard -> artifacts"
          />
        </SceneTransition>
      </Sequence>

      <Sequence from={scenes[1].from} durationInFrames={SCENE_LENGTH}>
        <SceneTransition>
          <SceneLayout eyebrow="Scene 1" title="Challenge Setup" subtitle="Organizer configures constraints and scoring posture">
            <div style={{display: 'flex', gap: 26, alignItems: 'flex-start'}}>
              <ApiPayloadCard title="Challenge Draft" method="POST" endpoint="/challenges" payload={challengePayload} />
              <div style={{display: 'grid', gap: 16}}>
                <MetricTile label="Iteration" value="30m" />
                <MetricTile label="Risk" value="Balanced" />
                <MetricTile label="Complexity" value="0.5" />
              </div>
            </div>
          </SceneLayout>
        </SceneTransition>
      </Sequence>

      <Sequence from={scenes[2].from} durationInFrames={SCENE_LENGTH}>
        <SceneTransition>
          <SceneLayout eyebrow="Scene 2" title="Run Start" subtitle="Deterministic seed is captured for replay-safe scoring">
            <ApiPayloadCard title="Run Started" method="POST" endpoint="/challenges/{id}/runs/start" payload={runStartPayload} />
          </SceneLayout>
        </SceneTransition>
      </Sequence>

      <Sequence from={scenes[3].from} durationInFrames={SCENE_LENGTH}>
        <SceneTransition>
          <SceneLayout eyebrow="Scene 3" title="Agent Execution" subtitle="Hacker and subagents execute in isolated sandboxes with budget guards">
            <ProgressRail />
          </SceneLayout>
        </SceneTransition>
      </Sequence>

      <Sequence from={scenes[4].from} durationInFrames={SCENE_LENGTH}>
        <SceneTransition>
          <SceneLayout eyebrow="Scene 4" title="Judge Ingestion + Safety Guardrails" subtitle="Mixed profile formats and URL ingestion with private-network redirect blocking">
            <div style={{display: 'flex', gap: 22}}>
              <ApiPayloadCard
                title="Bulk Judge Import"
                method="POST"
                endpoint="/challenges/{id}/judge-profiles/bulk"
                payload={'{"files":["panel.json","panel.yaml","panel.csv"],"accepted":3,"active_version":2}'}
              />
              <ApiPayloadCard
                title="URL Guard"
                method="POST"
                endpoint="/challenges/{id}/judge-profiles/url"
                payload={'{"status":"blocked","reason":"redirect blocked by URL sanitization"}'}
              />
            </div>
          </SceneLayout>
        </SceneTransition>
      </Sequence>

      <Sequence from={scenes[5].from} durationInFrames={SCENE_LENGTH}>
        <SceneTransition>
          <SceneLayout eyebrow="Scene 5" title="Checkpoint Scoring" subtitle="Novelty strategy, anti-gaming penalties, and weighted score composition">
            <ApiPayloadCard title="Scoring Payload" method="WORKER" endpoint="checkpoint_score" payload={scoringPayload} />
          </SceneLayout>
        </SceneTransition>
      </Sequence>

      <Sequence from={scenes[6].from} durationInFrames={SCENE_LENGTH}>
        <SceneTransition>
          <SceneLayout eyebrow="Scene 6" title="Replay + Diff Analytics" subtitle="Frozen snapshots replay deterministic score outputs for auditability">
            <ApiPayloadCard title="Replay Diff" method="POST" endpoint="/runs/{id}/replay" payload={replayPayload} />
          </SceneLayout>
        </SceneTransition>
      </Sequence>

      <Sequence from={scenes[7].from} durationInFrames={SCENE_LENGTH}>
        <SceneTransition>
          <SceneLayout eyebrow="Scene 7" title="Realtime Leaderboard" subtitle="Segment-aware ranking with stable cursor pagination under concurrent updates">
            <LeaderboardRows highlight={1} />
          </SceneLayout>
        </SceneTransition>
      </Sequence>

      <Sequence from={scenes[8].from} durationInFrames={SCENE_LENGTH}>
        <SceneTransition>
          <SceneLayout eyebrow="Scene 8" title="Artifact Retrieval + Quarantine" subtitle="Malware-blocked uploads are quarantined; approved artifacts use short-lived signed URLs">
            <div style={{display: 'flex', gap: 22}}>
              <ApiPayloadCard
                title="Artifact Download"
                method="GET"
                endpoint="/submissions/{id}/artifacts/{artifact_id}/download"
                payload={'{"url":"https://cdn.example/presigned/...","expires_in_seconds":300}'}
              />
              <ApiPayloadCard
                title="Quarantine Record"
                method="SECURITY"
                endpoint="storage/quarantine/{submission_id}"
                payload={'{"filename":"../evil.bin","reason":"signature:matched blocked signature","status":"stored"}'}
              />
            </div>
          </SceneLayout>
        </SceneTransition>
      </Sequence>

      <Sequence from={scenes[9].from} durationInFrames={SCENE_LENGTH}>
        <SceneTransition>
          <SceneLayout
            eyebrow="Outro"
            title="End-to-End Flow Completed"
            subtitle="From challenge definition to replayable ranking and artifact retrieval in 120 seconds"
            footer="Next: captions, narration sync, render pipeline, and QA checklist"
          />
        </SceneTransition>
      </Sequence>

      <GlobalProgress />
    </AbsoluteFill>
  );
};

const GlobalProgress: React.FC = () => {
  const frame = useCurrentFrame();
  const progress = interpolate(frame, [0, 3600], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: 0,
        height: 8,
        backgroundColor: 'rgba(18,35,41,0.12)',
      }}
    >
      <div style={{width: `${progress * 100}%`, height: '100%', backgroundColor: palette.accent}} />
    </div>
  );
};
