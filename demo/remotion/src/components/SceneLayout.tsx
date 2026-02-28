import React, {ReactNode} from 'react';

import {fontStack, palette} from '../theme';

type SceneLayoutProps = {
  eyebrow: string;
  title: string;
  subtitle?: string;
  children?: ReactNode;
  footer?: ReactNode;
};

export const SceneLayout: React.FC<SceneLayoutProps> = ({
  eyebrow,
  title,
  subtitle,
  children,
  footer,
}) => {
  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background: `radial-gradient(circle at 15% 20%, ${palette.accentSoft}, ${palette.paper} 45%, #f6ede1 100%)`,
        color: palette.ink,
        display: 'flex',
        flexDirection: 'column',
        padding: '64px 72px',
        boxSizing: 'border-box',
        fontFamily: fontStack.body,
      }}
    >
      <div style={{fontFamily: fontStack.mono, fontSize: 20, letterSpacing: 1.4, textTransform: 'uppercase'}}>{eyebrow}</div>
      <h1
        style={{
          margin: '18px 0 0',
          fontFamily: fontStack.display,
          fontSize: 64,
          lineHeight: 1.05,
          letterSpacing: -1,
          maxWidth: 1320,
        }}
      >
        {title}
      </h1>
      {subtitle ? (
        <p style={{margin: '18px 0 0', fontSize: 32, maxWidth: 1320, lineHeight: 1.25}}>{subtitle}</p>
      ) : null}
      <div style={{flex: 1, display: 'flex', alignItems: 'center', marginTop: 36}}>{children}</div>
      {footer ? <div style={{fontSize: 22}}>{footer}</div> : null}
    </div>
  );
};
