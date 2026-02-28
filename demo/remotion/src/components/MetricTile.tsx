import React from 'react';

import {fontStack, palette} from '../theme';

type MetricTileProps = {
  label: string;
  value: string;
};

export const MetricTile: React.FC<MetricTileProps> = ({label, value}) => {
  return (
    <div
      style={{
        backgroundColor: palette.panel,
        border: `2px solid ${palette.accentSoft}`,
        boxShadow: `0 10px 24px ${palette.shadow}`,
        borderRadius: 18,
        padding: '20px 24px',
        minWidth: 240,
      }}
    >
      <div style={{fontFamily: fontStack.mono, fontSize: 16, letterSpacing: 1.2, textTransform: 'uppercase'}}>{label}</div>
      <div style={{marginTop: 10, fontFamily: fontStack.display, fontSize: 42, lineHeight: 1}}>{value}</div>
    </div>
  );
};
