'use client';
import { useEffect, useRef, useState, type CSSProperties, type FormEvent } from 'react';
import type { Api } from '@/lib/api';
import { displayName, errorMessage, groupDigits } from '@/lib/format';
import type { Conversation, FingerprintInfo } from '@/lib/types';

interface Props {
  api: Api;
  conv: Conversation;
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}

export function VerifyDialog({ api, conv, open, onClose, onDone }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [fp, setFp] = useState<FingerprintInfo | null>(null);
  const [typed, setTyped] = useState('');
  const [error, setError] = useState<string | null>(null);
  // Tras confirmar, los bloques se sellan uno a uno antes de cerrar el diálogo.
  const [sealed, setSealed] = useState(false);

  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (!open) {
      if (dlg.open) dlg.close();
      return;
    }
    setTyped('');
    setError(null);
    setFp(null);
    setSealed(false);
    if (!dlg.open) dlg.showModal();
    api.fingerprint(conv.discord_id).then(setFp).catch((e) => setError(errorMessage(e)));
  }, [open, api, conv.discord_id]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api.verify(conv.discord_id, typed);
      onDone();
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return onClose();
      setSealed(true);
      setTimeout(onClose, 950);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <dialog ref={ref} onClose={onClose}>
      <form onSubmit={submit}>
        <h2>Verificar a {displayName(conv)}</h2>
        <p className="muted">
          Compara esta huella con la de tu contacto <b>fuera de Discord</b>: por llamada, en persona o por otro medio de confianza.
        </p>
        {/* Un bloque por grupo de 5 dígitos, en el mismo orden en que se dicta. */}
        <div
          className={`fp-big${fp ? '' : ' loading'}${sealed || (fp?.verified && !fp.key_pending) ? ' verified' : ''}`}
          data-testid="verify-fp"
          aria-label={fp ? `Huella: ${groupDigits(fp.fingerprint)}` : 'Cargando huella'}
        >
          {fp ? groupDigits(fp.fingerprint).split(' ').map((g, i) => <span key={i} className="fp-block" style={{ '--i': i } as CSSProperties}>{g}</span>) : '…'}
        </div>
        {fp?.key_pending && (
          <div className="alert bad">Esta es la huella de la llave <b>nueva</b>. Confírmala por otro medio antes de continuar.</div>
        )}
        {fp?.verified && !fp.key_pending ? (
          <p className="hint">Este contacto ya está verificado.</p>
        ) : (
          <label>
            Huella que te dicta tu contacto
            <input value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" required />
          </label>
        )}
        {error && <p className="error" role="alert">{error}</p>}
        <div className="row">
          <button type="button" className="ghost" onClick={onClose}>{fp?.verified && !fp.key_pending ? 'Cerrar' : 'Cancelar'}</button>
          {!(fp?.verified && !fp.key_pending) && <button className="primary" disabled={sealed}>Confirmar</button>}
        </div>
      </form>
    </dialog>
  );
}
