'use client';
import { Fragment, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import type { Api } from '@/lib/api';
import { displayName, errorMessage, groupDigits, messageMeta, sessionView } from '@/lib/format';
import type { Conversation, FingerprintInfo, Message } from '@/lib/types';

interface Props {
  api: Api;
  conv: Conversation;
  messages: Message[];
  fp: FingerprintInfo | null;
  onChanged: () => void;
  onVerify: () => void;
}

export function ChatPanel({ api, conv, messages, fp, onChanged, onVerify }: Props) {
  const [text, setText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);
  const view = sessionView(conv);

  useEffect(() => {
    const el = listRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [messages.length, conv.discord_id]);

  const send = async (e?: FormEvent) => {
    e?.preventDefault();
    const body = text.trim();
    if (!body) return;
    setError(null);
    try {
      await api.send(conv.discord_id, body);
      setText('');
      stickRef.current = true;
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  };

  const retry = async () => {
    try {
      await api.retry(conv.discord_id);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const name = displayName(conv);

  return (
    <div className="chat-panel">
      <header className="chat-head">
        <div className="head-row">
          <b>{name}</b>
          <span className={`badge ${view.lock.tone}`}>{view.lock.text}</span>
          {conv.verified ? <span className="badge ok">✓ Verificado</span> : <span className="badge off">Sin verificar</span>}
          <button className="ghost small" onClick={onVerify}>{conv.verified ? 'Ver huella' : 'Verificar'}</button>
        </div>
        {fp && <div className="fp">Huella de seguridad: {groupDigits(fp.fingerprint)}</div>}
      </header>

      {view.notice && (
        <div className={`alert${view.notice.kind === 'key' ? ' bad' : ''}`} role="alert">
          {view.notice.text}
          {view.notice.kind === 'retry' && <button className="small" onClick={retry}>Reintentar</button>}
          {view.notice.kind === 'key' && <button className="small" onClick={onVerify}>Volver a verificar</button>}
        </div>
      )}

      <div
        className="messages"
        ref={listRef}
        aria-live="polite"
        onScroll={(e) => {
          const el = e.currentTarget;
          stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
        }}
      >
        {messages.map((m) => {
          if (m.dir === 'sys') {
            return (
              <div key={m.id} className="sysbox warn">
                ⚠️ <b>Alerta de seguridad:</b> la llave pública de {name} cambió. La verificación previa se revocó automáticamente
                para prevenir ataques de intermediario.
              </div>
            );
          }
          if (m.status === 'undecryptable') {
            return (
              <Fragment key={m.id}>
                <div className="sysbox bad">
                  ⛔ <b>Mensaje no descifrable:</b> falló la verificación de autenticidad. El contenido fue descartado.
                </div>
                <div className="meta">{messageMeta(m, conv)}</div>
              </Fragment>
            );
          }
          return (
            <Fragment key={m.id}>
              <div className={`msg ${m.dir}`}>{m.text}{m.dir === 'out' && m.status !== 'queued' ? ' 🔒' : ''}</div>
              <div className={`meta ${m.dir}`}>{messageMeta(m, conv)}</div>
            </Fragment>
          );
        })}
      </div>

      {error && <p className="error composer-error" role="alert">{error}</p>}
      <form className="composer" onSubmit={send}>
        <textarea
          rows={1}
          maxLength={8000}
          placeholder="Escribe un mensaje cifrado de extremo a extremo..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKey}
          required
        />
        <button className="primary">Enviar 🔒</button>
      </form>
    </div>
  );
}
