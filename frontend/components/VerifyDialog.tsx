'use client';
import { useEffect, useRef, useState, type CSSProperties, type FormEvent, type KeyboardEvent, type SyntheticEvent } from 'react';
import type { Api } from '@/lib/api';
import {
  displayName, errorMessage, fingerprintFromDigest, FP_DIGITS, FP_GROUP_LEN, FP_GROUPS, groupDigits, parseQr, qrText,
} from '@/lib/format';
import type { Conversation, FingerprintInfo } from '@/lib/types';
import { QrCode, QrScanner } from './Qr';

interface Props {
  api: Api;
  conv: Conversation;
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}

// Tres formas de hacer la ceremonia. Dictar y escuchar van en pestañas separadas a propósito: mientras
// escribes lo que te dictan no tienes tu propia huella a la vista, así que no hay nada que transcribir.
type Mode = 'qr' | 'dictar' | 'escuchar';
const MODES: { id: Mode; label: string }[] = [
  { id: 'qr', label: 'Código QR' },
  { id: 'dictar', label: 'Dictar' },
  { id: 'escuchar', label: 'Escuchar' },
];
const EMPTY = Array.from({ length: FP_GROUPS }, () => '');
const block = (e: SyntheticEvent) => e.preventDefault();

export function VerifyDialog({ api, conv, open, onClose, onDone }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const boxes = useRef<(HTMLInputElement | null)[]>([]);
  const [fp, setFp] = useState<FingerprintInfo | null>(null);
  const [mode, setMode] = useState<Mode>('qr');
  const [groups, setGroups] = useState<string[]>(EMPTY);
  const [scanning, setScanning] = useState(false);
  const [busy, setBusy] = useState(false);
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
    setMode('qr');
    setGroups(EMPTY);
    setScanning(false);
    setBusy(false);
    setError(null);
    setFp(null);
    setSealed(false);
    if (!dlg.open) dlg.showModal();
    api.fingerprint(conv.discord_id).then(setFp).catch((e) => setError(errorMessage(e)));
  }, [open, api, conv.discord_id]);

  // Ya verificado: solo queda mostrar el código para que el otro haga su parte.
  const done = !!fp?.verified && !fp.key_pending;
  const typed = groups.join('');

  const change = (next: Mode) => {
    setMode(next);
    setScanning(false);
    setError(null);
  };

  const confirm = async (digits: string) => {
    setError(null);
    setBusy(true);
    try {
      await api.verify(conv.discord_id, digits);
      onDone();
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return onClose();
      setSealed(true);
      setTimeout(onClose, 950);
    } catch (err) {
      setError(errorMessage(err));
      setGroups(EMPTY);
      boxes.current[0]?.focus();
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (mode === 'escuchar' && typed.length === FP_DIGITS && !busy && !sealed) void confirm(typed);
  };

  const onScan = (text: string): boolean => {
    const digest = parseQr(text);
    if (!digest) {
      setError('Ese código QR no es una huella de esta aplicación.');
      return false;
    }
    setScanning(false);
    void confirm(fingerprintFromDigest(digest));
    return true;
  };

  const setGroup = (i: number, value: string) => {
    const digits = value.replace(/\D/g, '').slice(0, FP_GROUP_LEN);
    setGroups((g) => g.map((old, j) => (j === i ? digits : old)));
    if (digits.length === FP_GROUP_LEN) boxes.current[i + 1]?.focus();
  };

  const onBoxKey = (i: number, e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !groups[i]) boxes.current[i - 1]?.focus();
  };

  return (
    <dialog ref={ref} onClose={onClose}>
      <form onSubmit={submit}>
        <h2>Verificar a {displayName(conv)}</h2>
        <p className="muted">
          Hazlo <b>fuera de Discord</b>: en persona con el código QR, o por llamada dictando los dígitos.
          {' '}La verificación es de ida y vuelta: cada uno comprueba al otro.
        </p>
        {fp?.key_pending && (
          <div className="alert bad">Esta es la huella de la llave <b>nueva</b>. Confírmala por otro medio antes de continuar.</div>
        )}
        {done && <p className="hint">Ya verificaste a este contacto. Muéstrale tu código o díctaselo para que te verifique a ti.</p>}

        <div className="tabs" role="tablist" aria-label="Forma de verificar">
          {MODES.filter((m) => !(done && m.id === 'escuchar')).map((m) => (
            <button key={m.id} type="button" role="tab" aria-selected={mode === m.id} onClick={() => change(m.id)}>{m.label}</button>
          ))}
        </div>

        {!fp && <div className="fp-big loading">…</div>}

        {fp && mode === 'qr' && (
          <div className="qr-pair">
            <figure>
              <QrCode text={qrText(fp.qr)} label="Código QR de la huella de esta conversación" />
              <figcaption>Tu código: que tu contacto lo escanee</figcaption>
            </figure>
            {!done && (
              <figure>
                <div className={`qr-cam${sealed ? ' sealed' : ''}`}>
                  {scanning ? (
                    <QrScanner onText={onScan} onError={(m) => { setScanning(false); setError(m); }} />
                  ) : sealed ? (
                    <b>Coincide</b>
                  ) : (
                    <button type="button" className="small" disabled={busy} onClick={() => { setError(null); setScanning(true); }}>Abrir cámara</button>
                  )}
                </div>
                <figcaption>{scanning ? 'Apunta al código de tu contacto' : 'Escanea el código de tu contacto'}</figcaption>
              </figure>
            )}
          </div>
        )}

        {fp && mode === 'dictar' && (
          <>
            <p className="hint">Lee estos 12 grupos en voz alta, uno por uno. Tu contacto los escribe en «Escuchar».</p>
            {/* Un bloque por grupo de 5 dígitos, en el mismo orden en que se dicta. No se puede seleccionar ni copiar. */}
            <div
              className={`fp-big no-copy${sealed || done ? ' verified' : ''}`}
              data-testid="verify-fp"
              aria-label={`Huella: ${groupDigits(fp.fingerprint)}`}
              onCopy={block} onCut={block} onDragStart={block} onContextMenu={block}
            >
              {groupDigits(fp.fingerprint).split(' ').map((g, i) => <span key={i} className="fp-block" style={{ '--i': i } as CSSProperties}>{g}</span>)}
            </div>
          </>
        )}

        {fp && mode === 'escuchar' && !done && (
          <>
            <p className="hint">Escribe los grupos que te dicta tu contacto, 5 dígitos por casilla. No se puede pegar.</p>
            <div className={`fp-in${sealed ? ' sealed' : ''}`} role="group" aria-label="Huella que te dicta tu contacto">
              {groups.map((g, i) => (
                <input
                  key={i}
                  ref={(el) => { boxes.current[i] = el; }}
                  value={g}
                  onChange={(e) => setGroup(i, e.target.value)}
                  onKeyDown={(e) => onBoxKey(i, e)}
                  onPaste={block} onDrop={block}
                  inputMode="numeric" maxLength={FP_GROUP_LEN} autoComplete="off" spellCheck={false}
                  placeholder={String(i + 1).padStart(2, '0')}
                  aria-label={`Grupo ${i + 1} de ${FP_GROUPS}`}
                  disabled={busy || sealed}
                />
              ))}
            </div>
          </>
        )}

        {error && <p className="error" role="alert">{error}</p>}
        <div className="row">
          <button type="button" className="ghost" onClick={onClose}>{done ? 'Cerrar' : 'Cancelar'}</button>
          {mode === 'escuchar' && !done && (
            <button className="primary" disabled={busy || sealed || typed.length !== FP_DIGITS}>Confirmar</button>
          )}
        </div>
      </form>
    </dialog>
  );
}
