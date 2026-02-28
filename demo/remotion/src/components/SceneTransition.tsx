import React, {ReactNode} from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

type SceneTransitionProps = {
  children: ReactNode;
};

export const SceneTransition: React.FC<SceneTransitionProps> = ({children}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const entrance = spring({frame, fps, config: {damping: 20, stiffness: 120}});
  const opacity = interpolate(frame, [0, 10], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  return (
    <AbsoluteFill
      style={{
        opacity,
        transform: `translateY(${(1 - entrance) * 32}px)`,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};
