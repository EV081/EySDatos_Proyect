'use client';
import { useState, type FormEvent } from 'react';
import type { Api } from '@/lib/api';
import { errorMessage } from '@/lib/format';
import type { Status } from '@/lib/types';

type Mode = 'create' | 'import';

export function IdentityGate({ api, status, onStatus }: { api: Api; status: Status; onStatus: (s: Status) => void }) {
  const [mode, setMode] = useState<Mode>('create');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [id, setId] = useState('');
  const [pass, setPass] = useState('');
  const [pass2, setPass2] = useState('');
  const [file, setFile] = useState<File | null>(null);

  const run = async (action: () => Promise<Status>) => {
    setBusy(true);
    setError(null);
    try {
      onStatus(await action());
      setPass('');
      setPass2('');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const create = (e: FormEvent) => {
    e.preventDefault();
    if (pass !== pass2) return setError('Las contraseñas no coinciden.');
    void run(() => api.createIdentity(id.trim(), pass));
  };

  const doImport = (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    void run(async () => {
      let doc: { vault?: unknown };
      try {
        doc = JSON.parse(await file.text());
      } catch {
        throw { code: 'invalid' };
      }
      if (!doc.vault) throw { code: 'invalid' };
      return api.importIdentity(id.trim(), doc.vault, pass);
    });
  };

  const unlock = (e: FormEvent) => {
    e.preventDefault();
    void run(() => api.unlock(pass));
  };

  return (
    <section className="card center">
      <h1>Identidad</h1>
      {status.vault_exists ? (
        <form onSubmit={unlock}>
          <p className="muted">Ingresa tu contraseña maestra para abrir tu identidad.</p>
          <label>
            Contraseña maestra
            <input type="password" autoComplete="current-password" value={pass} onChange={(e) => setPass(e.target.value)} required autoFocus />
          </label>
          <button className="primary" disabled={busy}>Desbloquear</button>
        </form>
      ) : mode === 'create' ? (
        <form onSubmit={create}>
          <p className="muted">
            Tu identidad se genera en este dispositivo. La llave privada se cifra con tu contraseña maestra y nunca sale de aquí.
          </p>
          <label>
            Tu ID de Discord
            <input inputMode="numeric" pattern="[0-9]{1,25}" value={id} onChange={(e) => setId(e.target.value)} required />
          </label>
          <label>
            Contraseña maestra
            <input type="password" minLength={10} autoComplete="new-password" value={pass} onChange={(e) => setPass(e.target.value)} required />
          </label>
          <label>
            Repite la contraseña
            <input type="password" minLength={10} autoComplete="new-password" value={pass2} onChange={(e) => setPass2(e.target.value)} required />
          </label>
          <p className="hint">Mínimo 10 caracteres. Si la olvidas no hay forma de recuperarla.</p>
          <button className="primary" disabled={busy}>Crear identidad</button>
          <button type="button" className="link" onClick={() => { setMode('import'); setError(null); }}>
            Ya tengo una identidad exportada
          </button>
        </form>
      ) : (
        <form onSubmit={doImport}>
          <label>
            Tu ID de Discord
            <input inputMode="numeric" pattern="[0-9]{1,25}" value={id} onChange={(e) => setId(e.target.value)} required />
          </label>
          <label>
            Archivo de identidad (.json)
            <input type="file" accept="application/json,.json" onChange={(e) => setFile(e.target.files?.[0] ?? null)} required />
          </label>
          <label>
            Contraseña con la que se exportó
            <input type="password" autoComplete="off" value={pass} onChange={(e) => setPass(e.target.value)} required />
          </label>
          <button className="primary" disabled={busy}>Importar</button>
          <button type="button" className="link" onClick={() => { setMode('create'); setError(null); }}>Volver</button>
        </form>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  );
}
