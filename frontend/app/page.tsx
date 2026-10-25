'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Api } from '@/lib/api';
import { errorMessage } from '@/lib/format';
import type { Status } from '@/lib/types';
import { Banner } from '@/components/Banner';
import { ConnectForm } from '@/components/ConnectForm';
import { IdentityGate } from '@/components/IdentityGate';
import { Main } from '@/components/Main';

const KEY = 'e2ee.conn';

interface Conn {
  base: string;
  token: string;
}

// Solo http://127.0.0.1 o http://localhost: el token de la API local nunca debe ir a otro destino.
function isLocal(base: string): boolean {
  try {
    const u = new URL(base);
    return u.protocol === 'http:' && (u.hostname === '127.0.0.1' || u.hostname === 'localhost');
  } catch {
    return false;
  }
}

function loadConn(): Conn | null {
  // Para desarrollo: ?api=...&token=... se guarda en sessionStorage y se borra de la URL.
  const params = new URLSearchParams(window.location.search);
  const api = params.get('api');
  const token = params.get('token');
  if (api && token && isLocal(api)) {
    sessionStorage.setItem(KEY, JSON.stringify({ base: api, token }));
    window.history.replaceState(null, '', window.location.pathname);
  }
  try {
    const saved = JSON.parse(sessionStorage.getItem(KEY) ?? 'null') as Conn | null;
    return saved && isLocal(saved.base) ? saved : null;
  } catch {
    return null;
  }
}

export default function Page() {
  const [ready, setReady] = useState(false);
  const [conn, setConn] = useState<Conn | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    setConn(loadConn());
    setReady(true);
  }, []);

  const api = useMemo(() => (conn ? new Api(conn.base, conn.token) : null), [conn]);

  useEffect(() => {
    if (!api) return;
    let cancelled = false;
    api.status().then((s) => !cancelled && (setStatus(s), setError(null))).catch((e) => {
      if (cancelled) return;
      setError(errorMessage(e));
      if (e.code === 'unauthorized') {
        sessionStorage.removeItem(KEY);
        setConn(null);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [api]);

  const connect = (base: string, token: string) => {
    if (!isLocal(base)) return setError('La dirección debe ser http://127.0.0.1 o http://localhost.');
    sessionStorage.setItem(KEY, JSON.stringify({ base, token }));
    setConn({ base, token });
    setError(null);
  };

  const onLocked = useCallback(() => {
    if (!api) return;
    api.status().then(setStatus).catch(() => {});
  }, [api]);

  if (!ready) return null;

  return (
    <div className="app">
      <Banner text={error} />
      <Banner text={offline ? 'Sin conexión con el cliente local. Reintentando…' : null} info />
      {!api ? (
        <ConnectForm onConnect={connect} />
      ) : !status ? null : status.unlocked ? (
        <Main api={api} status={status} onLocked={onLocked} onOffline={setOffline} />
      ) : (
        <IdentityGate api={api} status={status} onStatus={setStatus} />
      )}
    </div>
  );
}
