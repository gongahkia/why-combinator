import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';

import {NarrationSyncPoint} from '../data/narrationSyncPoints';
import {fontStack, palette} from '../theme';

type CaptionOverlayProps = {
  syncPoints: NarrationSyncPoint[];
};

export const CaptionOverlay: React.FC<CaptionOverlayProps> = ({syncPoints}) => {
  const frame = useCurrentFrame();
  const activeCue = syncPoints.find((cue) => frame >= cue.startFrame && frame <= cue.endFrame);

  if (!activeCue) {
    return null;
  }

  const fadeInFrame = Math.min(activeCue.startFrame + 9, activeCue.endFrame);
  const fadeOutFrame = Math.max(activeCue.endFrame - 9, activeCue.startFrame);
  const opacity =
    frame <= fadeInFrame
      ? interpolate(frame, [activeCue.startFrame, fadeInFrame], [0, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        })
      : interpolate(frame, [fadeOutFrame, activeCue.endFrame], [1, 0], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'flex-end',
        alignItems: 'center',
        paddingBottom: 56,
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          width: 1600,
          maxWidth: '90%',
          borderRadius: 16,
          padding: '16px 22px',
          backgroundColor: 'rgba(18, 35, 41, 0.86)',
          boxShadow: `0 10px 26px ${palette.shadow}`,
          opacity,
        }}
      >
        <div
          style={{
            color: '#ffe8dc',
            fontFamily: fontStack.mono,
            fontSize: 14,
            letterSpacing: 0.8,
            textTransform: 'uppercase',
          }}
        >
          {`${activeCue.startSeconds}s - ${activeCue.endSeconds}s`}
        </div>
        <div
          style={{
            marginTop: 8,
            color: '#fffdf8',
            fontFamily: fontStack.body,
            fontSize: 34,
            lineHeight: 1.2,
          }}
        >
          {activeCue.caption}
        </div>
      </div>
    </AbsoluteFill>
  );
};
