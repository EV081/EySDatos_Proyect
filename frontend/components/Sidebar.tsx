'use client';
import { useState, type CSSProperties, type FormEvent } from 'react';
import type { Api } from '@/lib/api';
import { displayName, errorMessage, preview, sessionView } from '@/lib/format';
import type { Conversation } from '@/lib/types';
import { ThemeToggle } from './ThemeToggle';

// Color estable por contacto, derivado de su id (solo decorativo).
const hue = (id: string) => [...id].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) % 360, 7);

interface Props {
  api: Api;
  convs: Conversation[];
  selected: string | null;
  onSelect: (id: string) => void;
  onAdded: (id: string) => void;
  onIdentity: () => void;
}

export function Sidebar({ api, convs, selected, onSelect, onAdded, onIdentity }: Props) {
  const [adding, setAdding] = useState(false);
  const [id, setId] = useState('');
  const [alias, setAlias] = useState('');
  const [error, setError] = useState<string | null>(null);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const c = await api.addContact(id.trim(), alias.trim() || undefined);
      setId('');
      setAlias('');
      setAdding(false);
      onAdded(c.discord_id);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <aside className="side">
      <div className="side-head">
        <div className="brand"><span className="seal" aria-hidden="true" />Mensajería E2EE</div>
        <ThemeToggle />
      </div>
      <h2 className="side-title">Contactos</h2>
      {convs.length === 0 && <p className="no-contacts">Aún no tienes contactos.<br />Agrega el ID de Discord de alguien registrado.</p>}
      <ul className="contacts">
        {convs.map((c) => {
          const view = sessionView(c);
          const pill = c.verified ? { text: '✓ Verificado', tone: 'ok' } : view.pill;
          return (
            <li
              key={c.discord_id}
              className={`contact${selected === c.discord_id ? ' sel' : ''}${c.session === 'key_changed' ? ' alert-key' : ''}`}
              onClick={() => onSelect(c.discord_id)}
            >
              <div className="avatar" style={{ '--hue': hue(c.discord_id) } as CSSProperties}>{c.session === 'key_changed' ? '⚠️' : displayName(c)[0]?.toUpperCase()}</div>
              <div className="contact-main">
                <div className="contact-name">
                  {displayName(c)} {c.session === 'active' && <span title="Sesión cifrada activa">🔒</span>}
                </div>
                <div className="contact-sub">{preview(c.last)}</div>
              </div>
              {pill && <span className={`pill ${pill.tone}`}>{pill.text}</span>}
            </li>
          );
        })}
      </ul>
      {adding && (
        <form className="add" onSubmit={add}>
          <input placeholder="ID de Discord" inputMode="numeric" pattern="[0-9]{1,25}" value={id} onChange={(e) => setId(e.target.value)} required />
          <input placeholder="Nombre (opcional)" maxLength={64} value={alias} onChange={(e) => setAlias(e.target.value)} />
          <button className="primary small">Agregar</button>
          {error && <p className="error">{error}</p>}
        </form>
      )}
      <button className="ghost" onClick={() => setAdding((v) => !v)}>+ Agregar contacto</button>
      <button className="identity" onClick={onIdentity}>
        <span>⚙️ Gestión de identidad</span>
        <small>Ed25519</small>
      </button>
    </aside>
  );
}
