'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { Api } from '@/lib/api';
import type { Conversation, FingerprintInfo, Message, Status } from '@/lib/types';
import { ChatPanel } from './ChatPanel';
import { IdentityDialog } from './IdentityDialog';
import { Sidebar } from './Sidebar';
import { VerifyDialog } from './VerifyDialog';

const POLL_MS = 1500;

interface Props {
  api: Api;
  status: Status;
  onLocked: () => void;
  onOffline: (offline: boolean) => void;
}

export function Main({ api, status, onLocked, onOffline }: Props) {
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [fp, setFp] = useState<FingerprintInfo | null>(null);
  const [verifyOpen, setVerifyOpen] = useState(false);
  const [identityOpen, setIdentityOpen] = useState(false);
  const sigRef = useRef('');
  const refreshRef = useRef<() => Promise<void>>(async () => {});

  const conv = convs.find((c) => c.discord_id === selected) ?? null;

  useEffect(() => {
    let stopped = false;
    let busy = false;
    const tick = async () => {
      if (busy) return;
      busy = true;
      try {
        const list = await api.conversations();
        if (stopped) return;
        setConvs(list);
        if (selected && list.some((c) => c.discord_id === selected)) {
          // El historial completo, no solo lo nuevo: un mensaje "en cola" pasa a "enviado" sin cambiar de seq.
          const hist = await api.messages(selected, 0);
          const sig = JSON.stringify(hist);
          if (!stopped && sig !== sigRef.current) {
            sigRef.current = sig;
            setMessages(hist);
          }
        }
        onOffline(false);
      } catch (err) {
        const code = (err as { code?: string }).code;
        if (code === 'locked') onLocked();
        else if (code === 'network') onOffline(true);
      } finally {
        busy = false;
      }
    };
    refreshRef.current = tick;
    void tick();
    const timer = setInterval(tick, POLL_MS);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [api, selected, onLocked, onOffline]);

  // La huella se vuelve a pedir cuando cambia lo que la afecta (verificación o llave nueva).
  const fpKey = conv ? `${conv.discord_id}:${conv.verified}:${conv.session === 'key_changed'}` : '';
  useEffect(() => {
    if (!fpKey || !selected) {
      setFp(null);
      return;
    }
    let stale = false;
    api.fingerprint(selected).then((f) => !stale && setFp(f)).catch(() => !stale && setFp(null));
    return () => {
      stale = true;
    };
  }, [api, selected, fpKey]);

  const select = useCallback((id: string) => {
    sigRef.current = '';
    setMessages([]);
    setFp(null);
    setSelected(id);
  }, []);

  return (
    <section className="window">
      <Sidebar
        api={api}
        convs={convs}
        selected={selected}
        onSelect={select}
        onAdded={(id) => { select(id); void refreshRef.current(); }}
        onIdentity={() => setIdentityOpen(true)}
      />
      <main className="chat">
        {conv ? (
          <ChatPanel
            key={conv.discord_id}
            api={api}
            conv={conv}
            messages={messages}
            fp={fp}
            onChanged={() => void refreshRef.current()}
            onVerify={() => setVerifyOpen(true)}
          />
        ) : (
          <div className="empty">Selecciona o agrega un contacto para comenzar.</div>
        )}
      </main>
      {conv && (
        <VerifyDialog
          api={api}
          conv={conv}
          open={verifyOpen}
          onClose={() => setVerifyOpen(false)}
          onDone={() => void refreshRef.current()}
        />
      )}
      <IdentityDialog api={api} status={status} open={identityOpen} onClose={() => setIdentityOpen(false)} onLocked={onLocked} />
    </section>
  );
}
