export type NarrationSyncPoint = {
  id: string;
  startSeconds: number;
  endSeconds: number;
  startFrame: number;
  endFrame: number;
  caption: string;
};

export const narrationSyncPoints: NarrationSyncPoint[] = [
  {
    id: 'intro_hook',
    startSeconds: 0,
    endSeconds: 12,
    startFrame: 0,
    endFrame: 359,
    caption:
      'Autonomous orchestration takes a challenge from brief to judged leaderboard with deterministic scoring.',
  },
  {
    id: 'challenge_setup',
    startSeconds: 12,
    endSeconds: 24,
    startFrame: 360,
    endFrame: 719,
    caption:
      'Organizers set challenge constraints, risk posture, and quality targets before execution starts.',
  },
  {
    id: 'run_start',
    startSeconds: 24,
    endSeconds: 36,
    startFrame: 720,
    endFrame: 1079,
    caption:
      'Run start captures a deterministic seed and frozen snapshot for reproducible replay.',
  },
  {
    id: 'agent_execution',
    startSeconds: 36,
    endSeconds: 48,
    startFrame: 1080,
    endFrame: 1439,
    caption:
      'Hacker and subagents execute in isolated sandboxes with budget controls and checkpoints.',
  },
  {
    id: 'judge_ingestion',
    startSeconds: 48,
    endSeconds: 60,
    startFrame: 1440,
    endFrame: 1799,
    caption:
      'Judge profiles ingest from mixed formats while URL guards block unsafe redirect chains.',
  },
  {
    id: 'checkpoint_scoring',
    startSeconds: 60,
    endSeconds: 72,
    startFrame: 1800,
    endFrame: 2159,
    caption:
      'Checkpoint scoring blends quality and novelty with anti-gaming penalties.',
  },
  {
    id: 'replay_analytics',
    startSeconds: 72,
    endSeconds: 84,
    startFrame: 2160,
    endFrame: 2519,
    caption:
      'Replay diffs compare original and rerun outputs to confirm deterministic behavior.',
  },
  {
    id: 'leaderboard_realtime',
    startSeconds: 84,
    endSeconds: 96,
    startFrame: 2520,
    endFrame: 2879,
    caption:
      'Realtime leaderboard updates remain stable under concurrent writes and segment filters.',
  },
  {
    id: 'artifact_retrieval',
    startSeconds: 96,
    endSeconds: 108,
    startFrame: 2880,
    endFrame: 3239,
    caption:
      'Approved artifacts use short-lived signed URLs while blocked uploads are quarantined.',
  },
  {
    id: 'closing_cta',
    startSeconds: 108,
    endSeconds: 120,
    startFrame: 3240,
    endFrame: 3599,
    caption:
      'The flow is fully automated, observable, and reproducible in a two-minute demo.',
  },
];
