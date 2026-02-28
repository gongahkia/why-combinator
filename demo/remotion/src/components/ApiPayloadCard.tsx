import React from 'react';

import {fontStack, palette} from '../theme';

type ApiPayloadCardProps = {
  title: string;
  method: string;
  endpoint: string;
  payload: string;
};

export const ApiPayloadCard: React.FC<ApiPayloadCardProps> = ({title, method, endpoint, payload}) => {
  return (
    <div
      style={{
        backgroundColor: '#fff9f3',
        border: `2px solid ${palette.accentSoft}`,
        borderRadius: 18,
        padding: '18px 20px',
        width: 760,
        boxShadow: `0 12px 24px ${palette.shadow}`,
      }}
    >
      <div style={{fontFamily: fontStack.display, fontSize: 28, lineHeight: 1.1}}>{title}</div>
      <div style={{marginTop: 10, display: 'flex', gap: 10, alignItems: 'center'}}>
        <span
          style={{
            fontFamily: fontStack.mono,
            fontWeight: 700,
            fontSize: 14,
            letterSpacing: 1,
            backgroundColor: '#f26b3a',
            color: '#fff',
            borderRadius: 999,
            padding: '4px 10px',
            textTransform: 'uppercase',
          }}
        >
          {method}
        </span>
        <span style={{fontFamily: fontStack.mono, fontSize: 17}}>{endpoint}</span>
      </div>
      <pre
        style={{
          marginTop: 14,
          marginBottom: 0,
          padding: 14,
          borderRadius: 12,
          backgroundColor: '#1f2f37',
          color: '#dff7ff',
          fontFamily: fontStack.mono,
          fontSize: 16,
          lineHeight: 1.35,
          overflow: 'hidden',
          whiteSpace: 'pre-wrap',
        }}
      >
        {payload}
      </pre>
    </div>
  );
};
