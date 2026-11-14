export type SessionState = 'none' | 'handshaking' | 'active' | 'waiting' | 'unavailable' | 'key_changed';

export interface Message {
  seq: number;
  id: string;
  dir: 'in' | 'out' | 'sys';
  text: string | null;
  status: 'queued' | 'sent' | 'received' | 'undecryptable' | 'key_changed';
  ts: number;
  reason?: string;
}

export interface Conversation {
  discord_id: string;
  alias: string | null;
  verified: boolean;
  key_changed: boolean;
  session: SessionState;
  queued: number;
  last?: Message | null;
}

export interface Status {
  unlocked: boolean;
  vault_exists: boolean;
  discord_id: string | null;
  public_key: string | null;
}

export interface FingerprintInfo {
  fingerprint: string;
  qr: string;
  verified: boolean;
  key_pending: boolean;
}

// Derechos ARCO: lo que devuelve GET /privacy/my-data.
export interface LocalData {
  discord_id: string;
  public_key: string;
  consent: { version?: string; at?: number; withdrawn_at?: number } | null;
  contacts: { discord_id: string; alias: string | null; verified: boolean }[];
  messages: number;
  queued: number;
  data_dir: string;
}

export interface DirectoryRecord {
  discord_id: string;
  public_key: string;
  registered_at: string | null;
  key_changed_at: string | null;
  consent_version: string;
  consent_at: string | null;
  replaced_keys: { public_key: string; replaced_at: string | null; delete_after: string | null }[];
}

export interface MyData {
  local: LocalData;
  directory: DirectoryRecord | null;
  directory_error: 'login_required' | 'not_registered' | 'unavailable' | null;
}
