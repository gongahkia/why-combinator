import React from 'react';
import {Composition} from 'remotion';

import {MasterComposition} from './scenes/MasterComposition';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="DemoMaster"
        component={MasterComposition}
        durationInFrames={3600}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
