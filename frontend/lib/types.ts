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
