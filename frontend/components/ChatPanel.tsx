'use client';
import { Fragment, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import type { Api } from '@/lib/api';
import { displayName, errorMessage, messageMeta, sessionView } from '@/lib/format';
import type { Conversation, Message } from '@/lib/types';
import { Decipher } from './Cipher';
import { AlertIcon, BlockedIcon, CheckIcon, ExchangeIcon, LockIcon } from './Icons';

interface Props {
  api: Api;
  conv: Conversation;
  messages: Message[];
  /** El historial ya se cargó: lo que aparezca después es nuevo y se anima. */
  loaded: boolean;
  onChanged: () => void;
  onVerify: () => void;
  onRemoved: () => void;
}

export function ChatPanel({ api, conv, messages, loaded, onChanged, onVerify, onRemoved }: Props) {
  const [text, setText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [removing, setRemoving] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);
  const view = sessionView(conv);

  // Solo se anima lo que llega con el chat abierto, no el historial. La clave incluye el estado
  // para que un mensaje en cola que pasa a enviado también cierre su candado.
  const seenRef = useRef<Set<string> | null>(null);
  const freshRef = useRef(new Set<string>());
  const stamp = (m: Message) => `${m.id}:${m.status}`;
  if (loaded) {
    const first = seenRef.current === null;
    const seen = (seenRef.current ??= new Set<string>());
    for (const m of messages) {
      if (seen.has(stamp(m))) continue;
      seen.add(stamp(m));
      if (!first) freshRef.current.add(stamp(m));
    }
  }

  useEffect(() => {
    const el = listRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [messages.length, conv.discord_id]);

  const send = async (e?: FormEvent) => {
    e?.preventDefault();
    const body = text.trim();
    if (!body || !conv.verified) return;
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

  const remove = async () => {
    setRemoving(true);
    setError(null);
    try {
      await api.removeContact(conv.discord_id);
      onRemoved();
    } catch (err) {
      setError(errorMessage(err));
      setRemoving(false);
      setConfirmRemove(false);
    }
  };

  const name = displayName(conv);

  return (
    <div className="chat-panel">
      <header className="chat-head">
        <div className="head-row">
          <b>{name}</b>
          <span className={`badge ${view.lock.tone}`}>
            {conv.session === 'active' && <LockIcon />}
            {conv.session === 'handshaking' && <ExchangeIcon />}
            {conv.session === 'key_changed' && <AlertIcon />}
            {view.lock.text}
          </span>
          {conv.verified ? <span className="badge ok"><CheckIcon />Verificado</span> : <span className="badge off">Sin verificar</span>}
          <button className="ghost small" onClick={onVerify}>{conv.verified ? 'Ver huella' : 'Verificar'}</button>
          <button className="ghost small" onClick={() => setConfirmRemove(true)} disabled={confirmRemove}>Quitar</button>
        </div>
      </header>

      {confirmRemove && (
        <div className="alert bad" role="alertdialog" aria-label={`Quitar a ${name}`}>
          ¿Quitar a {name}? Se borran de este dispositivo la conversación, la verificación y lo que esté en cola. No se puede
          deshacer. Si te vuelve a escribir, aparecerá como contacto sin verificar.
          <span className="alert-actions">
            <button className={`small danger${removing ? ' busy' : ''}`} onClick={remove} disabled={removing}>Quitar contacto</button>
            <button className="small ghost" onClick={() => setConfirmRemove(false)} disabled={removing}>Cancelar</button>
          </span>
        </div>
      )}

      {!conv.verified && view.notice?.kind !== 'key' && (
        <div className="alert bad" role="alert" data-testid="verify-required">
          Verifica la huella de {name} para conversar. Sin esa verificación no se envía ni se recibe ningún mensaje.
          <button className="small" onClick={onVerify}>Verificar ahora</button>
        </div>
      )}

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
                <AlertIcon /> <b>Alerta de seguridad:</b> la llave pública de {name} cambió. La verificación previa se revocó automáticamente
                para prevenir ataques de intermediario.
              </div>
            );
          }
          if (m.status === 'undecryptable') {
            return (
              <Fragment key={m.id}>
                <div className="sysbox bad">
                  <BlockedIcon /> <b>Mensaje no descifrable:</b> falló la verificación de autenticidad. El contenido fue descartado.
                </div>
                <div className="meta">{messageMeta(m, conv)}</div>
              </Fragment>
            );
          }
          const fresh = freshRef.current.has(stamp(m));
          return (
            <Fragment key={m.id}>
              <div className={`msg ${m.dir}`}>{fresh && m.dir === 'in' && m.text ? <Decipher text={m.text} /> : m.text}</div>
              <div className={`meta ${m.dir}${fresh ? ' fresh' : ''}`}>
                {m.dir === 'out' && m.status !== 'queued' && <LockIcon size={12} />}
                {messageMeta(m, conv)}
              </div>
            </Fragment>
          );
        })}
      </div>

      {error && <p className="error composer-error" role="alert">{error}</p>}
      <form className="composer" onSubmit={send}>
        <textarea
          rows={1}
          maxLength={8000}
          placeholder={conv.verified ? 'Escribe un mensaje cifrado de extremo a extremo...' : 'Verifica la huella para poder escribir'}
          disabled={!conv.verified}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKey}
          required
        />
        <button className="primary" disabled={!conv.verified}>Enviar</button>
      </form>
    </div>
  );
}
