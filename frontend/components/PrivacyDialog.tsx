'use client';
import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import type { Api } from '@/lib/api';
import { directoryErrorText, errorMessage, formatDate } from '@/lib/format';
import type { MyData, Status } from '@/lib/types';

interface Props {
  api: Api;
  open: boolean;
  onClose: () => void;
  /** La identidad cambió (llave nueva, registro cancelado o datos borrados): hay que releer el estado. */
  onStatus: (s: Status) => void;
}

type Action = 'rotate' | 'cancel' | 'wipe';

const LOGIN_HINT = 'Si usas el directorio real, antes completa Discord y Microsoft Authenticator (python -m directory.client_lib.login): el token vale 10 minutos.';

/** Derechos ARCO: acceso, rectificación, cancelación/oposición y borrado de los datos de este dispositivo. */
export function PrivacyDialog({ api, open, onClose, onStatus }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [data, setData] = useState<MyData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.myData());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (open && !dlg.open) {
      setNotice(null);
      setData(null);
      dlg.showModal();
      void load();
    } else if (!open && dlg.open) {
      dlg.close();
    }
  }, [open, load]);

  const download = () => {
    if (!data) return;
    const file = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(file);
    const link = document.createElement('a');
    link.href = url;
    link.download = `mis-datos-${data.local.discord_id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const done = (status: Status, message: string) => {
    if (!status.unlocked || !status.vault_exists) {
      onClose();
      onStatus(status);
      return;
    }
    setNotice(message);
    onStatus(status);
    void load();
  };

  const local = data?.local;
  const dir = data?.directory;
  const dirError = directoryErrorText(data?.directory_error ?? null);

  return (
    <dialog ref={ref} onClose={onClose} className="wide" aria-labelledby="arco-title">
      <h2 id="arco-title">Mis datos y derechos ARCO</h2>
      <p className="muted">
        Según la Ley N.° 29733 puedes ver, corregir y borrar tus datos, u oponerte a su uso.{' '}
        <a className="out" href="/politica-de-privacidad" target="_blank" rel="noopener noreferrer">Leer la política</a>
      </p>
      {notice && <p className="ok-note" role="status">{notice}</p>}

      <section className="arco">
        <h3><span className="arco-letter">A</span> Acceso: lo que hay de ti</h3>
        {loading && <p className="muted">Cargando…</p>}
        {local && (
          <>
            <h4>En este dispositivo</h4>
            <dl className="kv">
              <dt>ID de Discord</dt><dd>{local.discord_id}</dd>
              <dt>Llave pública</dt><dd><code className="pk">{local.public_key}</code></dd>
              <dt>Aviso aceptado</dt>
              <dd>
                {local.consent?.version ? `Versión ${local.consent.version}, el ${formatDate(local.consent.at)}` : '—'}
                {local.consent?.withdrawn_at ? ` · retirado el ${formatDate(local.consent.withdrawn_at)}` : ''}
              </dd>
              <dt>Contactos</dt><dd>{local.contacts.length} ({local.contacts.filter((c) => c.verified).length} verificados)</dd>
              <dt>Mensajes guardados</dt><dd>{local.messages} ({local.queued} en cola)</dd>
              <dt>Carpeta</dt><dd><code>{local.data_dir}</code></dd>
            </dl>
            <h4>En el directorio</h4>
            {dirError && <p className="hint">{dirError}</p>}
            {dir && (
              <dl className="kv">
                <dt>Llave publicada</dt><dd><code className="pk">{dir.public_key}</code></dd>
                <dt>Registrado</dt><dd>{formatDate(dir.registered_at)}</dd>
                <dt>Último cambio de llave</dt><dd>{formatDate(dir.key_changed_at)}</dd>
                <dt>Aviso aceptado</dt><dd>Versión {dir.consent_version}, el {formatDate(dir.consent_at)}</dd>
                {dir.mfa && <>
                  <dt>Microsoft Authenticator</dt><dd>{dir.mfa.enabled ? 'Activado' : 'Pendiente de confirmar'}</dd>
                  <dt>Códigos de recuperación</dt><dd>{dir.mfa.recovery_codes_remaining} disponibles</dd>
                </>}
                <dt>Llaves anteriores</dt>
                <dd>
                  {dir.replaced_keys.length === 0
                    ? 'Ninguna'
                    : dir.replaced_keys.map((k) => (
                        <span key={k.public_key} className="replaced">
                          Reemplazada el {formatDate(k.replaced_at)}
                          {k.delete_after ? `; se borra el ${formatDate(k.delete_after)}` : ''}
                        </span>
                      ))}
                </dd>
              </dl>
            )}
            <p className="hint">El contenido de tus mensajes y tu llave privada no están en el directorio: solo existen en este dispositivo.</p>
            <div className="row start">
              <button className="ghost small" onClick={() => void load()} disabled={loading}>Actualizar</button>
              <button className="ghost small" onClick={download}>Descargar mis datos (JSON)</button>
            </div>
          </>
        )}
      </section>

      <ArcoAction
        letter="R"
        title="Rectificación: cambiar mi llave"
        action="rotate"
        text="Genera una llave nueva y la publica en lugar de la anterior, que la autoriza con su firma. Tu historial se conserva. Úsalo si crees que tu llave se vio comprometida."
        confirm="Entiendo que mis contactos verán una alerta de cambio de llave y deberán volver a verificarme."
        button="Cambiar mi llave"
        run={async (password) => done(await api.rotateKey(password), 'Listo: tu llave nueva ya está publicada. Pide a tus contactos que vuelvan a verificar tu huella.')}
      />

      <ArcoAction
        letter="C·O"
        title="Cancelación y oposición: retirar mi consentimiento"
        action="cancel"
        text="Borra tu registro del directorio de inmediato (de las copias de seguridad, en un máximo de 30 días). Nadie podrá volver a encontrarte para escribirte."
        confirm="Entiendo que esto no se puede deshacer."
        button="Cancelar mi registro"
        danger
        withDeleteLocal
        run={async (password, deleteLocal) =>
          done(await api.cancelRegistration(password, deleteLocal), 'Tu registro se borró del directorio. Tus datos de este dispositivo se conservan.')}
      />

      <ArcoAction
        letter="C"
        title="Borrar mis datos de este dispositivo"
        action="wipe"
        text="Borra tu identidad, tus contactos y tu historial de este dispositivo. No borra tu registro del directorio: para eso usa la opción anterior. Exporta tu identidad antes si quieres conservarla."
        confirm="Entiendo que sin un respaldo exportado perderé mi identidad y mi historial."
        button="Borrar datos del dispositivo"
        danger
        run={async (password) => done(await api.deleteLocalData(password), '')}
      />

      {error && <p className="error" role="alert">{error}</p>}
      <div className="row">
        <button className="primary" onClick={onClose}>Cerrar</button>
      </div>
    </dialog>
  );
}

interface ActionProps {
  letter: string;
  title: string;
  action: Action;
  text: string;
  confirm: string;
  button: string;
  danger?: boolean;
  withDeleteLocal?: boolean;
  run: (password: string, deleteLocal: boolean) => Promise<void>;
}

function ArcoAction({ letter, title, action, text, confirm, button, danger, withDeleteLocal, run }: ActionProps): ReactNode {
  const [pass, setPass] = useState('');
  const [sure, setSure] = useState(false);
  const [deleteLocal, setDeleteLocal] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await run(pass, deleteLocal);
      setPass('');
      setSure(false);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <details className="arco">
      <summary><span className="arco-letter">{letter}</span> {title}</summary>
      <form onSubmit={submit}>
        <p className="muted">{text}</p>
        {action !== 'wipe' && <p className="hint">{LOGIN_HINT}</p>}
        <label>
          Contraseña maestra
          <input type="password" autoComplete="current-password" value={pass} onChange={(e) => setPass(e.target.value)} required />
        </label>
        {withDeleteLocal && (
          <label className="check">
            <input type="checkbox" checked={deleteLocal} onChange={(e) => setDeleteLocal(e.target.checked)} />
            <span>Borrar también mi identidad, contactos e historial de este dispositivo.</span>
          </label>
        )}
        <label className="check">
          <input type="checkbox" checked={sure} onChange={(e) => setSure(e.target.checked)} required />
          <span>{confirm}</span>
        </label>
        <button className={`${danger ? 'danger' : 'primary'}${busy ? ' busy' : ''}`} disabled={busy || !sure}>{button}</button>
        {error && <p className="error" role="alert">{error}</p>}
      </form>
    </details>
  );
}
