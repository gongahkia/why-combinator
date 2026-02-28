import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';

import {MetricTile} from '../components/MetricTile';
import {SceneLayout} from '../components/SceneLayout';

const SCENE = {
  intro: 0,
  setup: 600,
  execution: 1200,
  judging: 1800,
  leaderboard: 2400,
  outro: 3000,
};

export const MasterComposition: React.FC = () => {
  return (
    <AbsoluteFill>
      <Sequence from={SCENE.intro} durationInFrames={600}>
        <SceneLayout
          eyebrow="Hackathon Service"
          title="Autonomous Build-to-Judge Pipeline"
          subtitle="120-second product walkthrough master composition"
          footer="Scene primitives and timeline scaffold initialized"
        />
      </Sequence>

      <Sequence from={SCENE.setup} durationInFrames={600}>
        <SceneLayout
          eyebrow="Scene 1"
          title="Challenge Setup"
          subtitle="Organizer defines challenge goals, constraints, and scoring profile"
        >
          <div style={{display: 'flex', gap: 20}}>
            <MetricTile label="Window" value="30m" />
            <MetricTile label="Risk" value="Balanced" />
            <MetricTile label="Complexity" value="0.5" />
          </div>
        </SceneLayout>
      </Sequence>

      <Sequence from={SCENE.execution} durationInFrames={600}>
        <SceneLayout
          eyebrow="Scene 2"
          title="Run Start + Agent Execution"
          subtitle="Scheduler dispatches deterministic runs and traces subagent activity"
        />
      </Sequence>

      <Sequence from={SCENE.judging} durationInFrames={600}>
        <SceneLayout
          eyebrow="Scene 3"
          title="Judging + Checkpoint Scoring"
          subtitle="Judge panel scores submissions with policy-aware novelty controls"
        />
      </Sequence>

      <Sequence from={SCENE.leaderboard} durationInFrames={600}>
        <SceneLayout
          eyebrow="Scene 4"
          title="Leaderboard + Artifacts"
          subtitle="Realtime ranking, replayable scoring, and signed artifact retrieval"
        />
      </Sequence>

      <Sequence from={SCENE.outro} durationInFrames={600}>
        <SceneLayout
          eyebrow="Outro"
          title="Demo Pipeline Ready"
          subtitle="Storyboard, visuals, transitions, and render automation continue in follow-up tasks"
        />
      </Sequence>
    </AbsoluteFill>
  );
};
