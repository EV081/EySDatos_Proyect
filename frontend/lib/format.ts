// Funciones puras de presentación (sin DOM ni React), para probarlas con `node --test`.
import type { Conversation, Message } from './types.ts';

const ERRORS: Record<string, string> = {
  network: 'No hay conexión con el cliente local.',
  unauthorized: 'El token de la API local no es válido.',
  locked: 'Desbloquea tu identidad con tu contraseña maestra.',
  bad_password: 'Contraseña incorrecta.',
  too_many_attempts: 'Demasiados intentos. Espera unos segundos.',
  not_found: 'No se encontró lo que buscas.',
  conflict: 'La operación no se pudo completar.',
  key_changed: 'La llave del contacto cambió: hay que verificar la nueva huella.',
  peer_key_unavailable: 'No se pudo obtener la llave del contacto (¿está registrado en el directorio?).',
  invalid: 'Revisa los datos ingresados.',
};

export function errorMessage(err: unknown): string {
  const e = err as { code?: string; message?: string } | null;
  if (!e || !e.code) return 'Ocurrió un error.';
  // Los detalles del cliente local ya vienen en español y no contienen datos internos.
  if (e.code === 'conflict' && e.message && e.message !== 'conflict') return e.message;
  return ERRORS[e.code] ?? ERRORS.conflict;
}

export type Tone = 'ok' | 'brand' | 'wait' | 'off' | 'bad';

export interface SessionView {
  lock: { text: string; tone: Tone };
  pill: { text: string; tone: Tone } | null;
  notice: { kind: 'info' | 'retry' | 'key'; text: string } | null;
}

// Estado de la sesión de un contacto -> candado del encabezado, insignia de la lista y aviso del chat.
export function sessionView(contact: Pick<Conversation, 'session'>): SessionView {
  switch (contact.session) {
    case 'active':
      return { lock: { text: 'Cifrado E2EE', tone: 'brand' }, pill: null, notice: null };
    case 'handshaking':
      return { lock: { text: 'Estableciendo sesión…', tone: 'wait' }, pill: { text: 'Handshake', tone: 'wait' }, notice: null };
    case 'waiting':
      return {
        lock: { text: 'Sin sesión', tone: 'off' }, pill: { text: 'Esperando', tone: 'wait' },
        notice: { kind: 'info', text: 'Tu contacto no respondió. Los mensajes esperan en cola y se reintentará automáticamente.' },
      };
    case 'unavailable':
      return {
        lock: { text: 'Sin sesión', tone: 'off' }, pill: { text: 'No disponible', tone: 'bad' },
        notice: { kind: 'retry', text: 'No se pudo contactar a esta persona. Los mensajes siguen en cola.' },
      };
    case 'key_changed':
      return {
        lock: { text: 'Llave cambiada', tone: 'wait' }, pill: { text: 'Llave cambió', tone: 'bad' },
        notice: { kind: 'key', text: 'La llave pública de este contacto cambió. La verificación fue revocada y no se enviará nada hasta que verifiques la nueva huella.' },
      };
    default:
      return { lock: { text: 'Sin sesión', tone: 'off' }, pill: null, notice: null };
  }
}

export const displayName = (c: Pick<Conversation, 'alias' | 'discord_id'>): string => c.alias || c.discord_id;

export function preview(last: Message | null | undefined): string {
  if (!last) return 'Sin mensajes';
  if (last.dir === 'sys') return 'Alerta de seguridad';
  if (last.status === 'undecryptable') return 'Mensaje no descifrable';
  return last.text ?? '';
}

export function formatTime(ts: number): string {
  const d = new Date(ts * 1000);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export function messageMeta(m: Message, contact: Pick<Conversation, 'verified'>): string {
  const t = formatTime(m.ts);
  if (m.dir === 'out') {
    return m.status === 'queued' ? `${t} · En cola: se enviará al establecer la sesión` : `${t} · Cifrado AES-256-GCM`;
  }
  if (m.status === 'undecryptable') return `${t} · Error de integridad`;
  return `${t} · ${contact.verified ? 'Verificado' : 'Sin verificar'}`;
}

// La huella leída puede venir con espacios, guiones o saltos de línea.
export const normalizeFingerprint = (text: string): string => String(text).replace(/\D/g, '');

// La huella se muestra en grupos de 5 dígitos, igual que en la ceremonia.
export function groupDigits(digits: string): string {
  return normalizeFingerprint(digits).replace(/(\d{5})(?=\d)/g, '$1 ');
}
