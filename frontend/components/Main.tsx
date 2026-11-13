'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { Api } from '@/lib/api';
import type { Conversation, Message, Status } from '@/lib/types';
import { ChatPanel } from './ChatPanel';
import { CipherStream } from './Cipher';
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
  const [loaded, setLoaded] = useState(false);
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
          if (stopped) return;
          if (sig !== sigRef.current) {
            sigRef.current = sig;
            setMessages(hist);
          }
          setLoaded(true);
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

  const select = useCallback((id: string) => {
    sigRef.current = '';
    setMessages([]);
    setLoaded(false);
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
            loaded={loaded}
            onChanged={() => void refreshRef.current()}
            onVerify={() => setVerifyOpen(true)}
          />
        ) : (
          <div className="empty">
            <b><span className="rd">Tus mensajes, solo tuyos</span></b>
            Selecciona o agrega un contacto para comenzar una conversación cifrada de extremo a extremo.
            <CipherStream />
            <span className="cipher-cap">Esto es lo único que Discord llega a ver.</span>
          </div>
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
