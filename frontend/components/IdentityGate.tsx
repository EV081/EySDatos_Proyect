'use client';
import { useState, type FormEvent } from 'react';
import type { Api } from '@/lib/api';
import { errorMessage } from '@/lib/format';
import { NOTICE_VERSION } from '@/lib/privacy';
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
  const [accepted, setAccepted] = useState(false);

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


  const consent = (
    <>
      <details className="notice">
        <summary>Aviso de privacidad (versión {NOTICE_VERSION})</summary>
        <p>
          <a className="out" href="/privacidad" target="_blank" rel="noopener noreferrer">Leer el aviso completo</a>
        </p>
        <ul>
          <li><b>Qué se publica:</b> tu ID de Discord y tu llave pública de firma, en un directorio. Es lo único que el directorio guarda de ti, junto con las fechas de registro.</li>
          <li><b>Para qué:</b> solo para que otras personas encuentren tu llave y puedan escribirte de forma cifrada. No se usa para publicidad ni análisis.</li>
          <li><b>Qué no ve nadie más:</b> el contenido de tus mensajes y tu llave privada nunca salen de tu dispositivo. Discord solo guarda texto cifrado.</li>
          <li><b>Qué sí se puede ver:</b> quién se comunica con quién y cuándo (los metadatos) es visible para Discord y para quienes están en el canal.</li>
          <li><b>Tus derechos:</b> puedes pedir acceso, rectificación, cancelación u oposición, y exportar tu identidad, en cualquier momento.</li>
        </ul>
      </details>
      <label className="check">
        <input type="checkbox" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} required />
        <span>Acepto el aviso de privacidad: que mi ID de Discord y mi llave pública se publiquen en el directorio con esa finalidad, y declaro ser mayor de edad.</span>
      </label>
    </>
  );

  const create = (e: FormEvent) => {
    e.preventDefault();
    if (pass !== pass2) return setError('Las contraseñas no coinciden.');
    void run(() => api.createIdentity(id.trim(), pass, NOTICE_VERSION));
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
      return api.importIdentity(id.trim(), doc.vault, pass, NOTICE_VERSION);
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
          {consent}
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
          {consent}
          <button className="primary" disabled={busy}>Importar</button>
          <button type="button" className="link" onClick={() => { setMode('create'); setError(null); }}>Volver</button>
        </form>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  );
}
