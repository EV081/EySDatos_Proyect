'use client';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import type { Api } from '@/lib/api';
import { errorMessage } from '@/lib/format';
import type { Status } from '@/lib/types';

interface Props {
  api: Api;
  status: Status;
  open: boolean;
  onClose: () => void;
  onLocked: () => void;
}

export function IdentityDialog({ api, status, open, onClose, onLocked }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [pass, setPass] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (open && !dlg.open) {
      setPass('');
      setError(null);
      dlg.showModal();
    } else if (!open && dlg.open) {
      dlg.close();
    }
  }, [open]);

  const exportIdentity = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const { vault } = await api.exportIdentity(pass);
      const file = new Blob([JSON.stringify({ discord_id: status.discord_id, vault }, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(file);
      const link = document.createElement('a');
      link.href = url;
      link.download = `identidad-${status.discord_id}.json`;
      link.click();
      URL.revokeObjectURL(url);
      setPass('');
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const lock = async () => {
    try {
      await api.lock();
      onClose();
      onLocked();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <dialog ref={ref} onClose={onClose}>
      <h2>Gestión de identidad</h2>
      <p className="muted">Tu ID de Discord: <b>{status.discord_id}</b></p>
      <p className="muted">Llave pública de firma (Ed25519):</p>
      <code className="pk">{status.public_key}</code>
      <form onSubmit={exportIdentity}>
        <label>
          Contraseña para el archivo exportado
          <input type="password" minLength={10} autoComplete="new-password" value={pass} onChange={(e) => setPass(e.target.value)} required />
        </label>
        <button className="ghost">Exportar identidad</button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="row">
        <button className="ghost" onClick={lock}>Bloquear</button>
        <button className="primary" onClick={onClose}>Cerrar</button>
      </div>
    </dialog>
  );
}
