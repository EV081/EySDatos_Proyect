// Iconos de trazo fino dibujados a mano (sin emojis ni fuentes de iconos). Heredan el color del texto.
import type { ReactNode } from 'react';

function Ico({ children, size = 14 }: { children: ReactNode; size?: number }) {
  return (
    <svg
      className="ico" width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor"
      strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
    >
      {children}
    </svg>
  );
}

// El arco del candado tiene su propia clase: el CSS lo anima cerrándose.
export const LockIcon = ({ size }: { size?: number }) => (
  <Ico size={size}>
    <path className="shackle" d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" />
    <rect x="3" y="7" width="10" height="7" rx="1.5" />
  </Ico>
);

export const CheckIcon = () => (
  <Ico>
    <path className="draw" pathLength={1} d="M3 8.5l3.2 3.2L13 4.5" />
  </Ico>
);

export const AlertIcon = ({ size }: { size?: number }) => (
  <Ico size={size}>
    <path d="M8 2.5l6.5 11h-13z" />
    <path d="M8 6.8v3M8 11.9v.1" />
  </Ico>
);

export const BlockedIcon = () => (
  <Ico>
    <circle cx="8" cy="8" r="5.5" />
    <path d="M4.1 4.1l7.8 7.8" />
  </Ico>
);

export const KeyIcon = () => (
  <Ico>
    <circle cx="5" cy="11" r="2.5" />
    <path d="M6.8 9.2L13 3M10.5 5.5l2 2" />
  </Ico>
);

export const SunIcon = () => (
  <Ico size={17}>
    <circle cx="8" cy="8" r="2.8" />
    <path d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1" />
  </Ico>
);

export const MoonIcon = () => (
  <Ico size={17}>
    <path d="M13.2 9.6A5.6 5.6 0 0 1 6.4 2.8a5.6 5.6 0 1 0 6.8 6.8z" />
  </Ico>
);

// Intercambio de llaves en curso: un punto viaja entre las dos partes.
export const ExchangeIcon = () => <span className="exchange" aria-hidden="true"><i /></span>;
