// Cliente HTTP de la API local (docs/api/client.openapi.json). No guarda nada: el token lo conserva
// la app solo en sessionStorage.
import type { Conversation, FingerprintInfo, Message, Status } from './types.ts';

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, detail = '') {
    super(detail || code);
    this.status = status;
    this.code = code;
  }
}

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export class Api {
  private base: string;
  private token: string;
  private fetchImpl: FetchLike;

  constructor(base: string, token: string, fetchImpl: FetchLike = (i, o) => fetch(i, o)) {
    this.base = base.replace(/\/+$/, '');
    this.token = token;
    this.fetchImpl = fetchImpl;
  }

  async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    let res: Response;
    try {
      res = await this.fetchImpl(this.base + path, {
        method,
        headers: {
          Authorization: `Bearer ${this.token}`,
          ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
        cache: 'no-store',
      });
    } catch {
      throw new ApiError(0, 'network', 'No hay conexión con el cliente local');
    }
    if (res.status === 204) return null as T;
    let data: { error?: string; detail?: unknown } | null = null;
    try {
      data = await res.json();
    } catch {
      /* respuesta sin cuerpo JSON */
    }
    if (!res.ok) {
      const code = data?.error || (res.status === 401 ? 'unauthorized' : res.status === 422 ? 'invalid' : 'error');
      throw new ApiError(res.status, code, typeof data?.detail === 'string' ? data.detail : '');
    }
    return data as T;
  }

  status = () => this.request<Status>('GET', '/status');
  createIdentity = (discordId: string, password: string, consentVersion: string) =>
    this.request<Status>('POST', '/identity', { discord_id: discordId, password, consent_version: consentVersion });
  importIdentity = (discordId: string, vault: unknown, password: string, consentVersion: string) =>
    this.request<Status>('POST', '/identity/import', { discord_id: discordId, vault, password, consent_version: consentVersion });
  unlock = (password: string) => this.request<Status>('POST', '/identity/unlock', { password });
  lock = () => this.request<null>('POST', '/identity/lock');
  exportIdentity = (password: string) => this.request<{ vault: unknown }>('POST', '/identity/export', { password });
  conversations = () => this.request<Conversation[]>('GET', '/conversations');
  addContact = (discordId: string, alias?: string) =>
    this.request<Conversation>('POST', '/contacts', { discord_id: discordId, alias: alias || null });
  fingerprint = (id: string) => this.request<FingerprintInfo>('GET', `/contacts/${encodeURIComponent(id)}/fingerprint`);
  verify = (id: string, fingerprint: string) =>
    this.request<Conversation>('POST', `/contacts/${encodeURIComponent(id)}/verify`, { fingerprint });
  messages = (id: string, since: number) =>
    this.request<Message[]>('GET', `/conversations/${encodeURIComponent(id)}/messages?since=${since | 0}`);
  send = (id: string, text: string) =>
    this.request<Conversation>('POST', `/conversations/${encodeURIComponent(id)}/messages`, { text });
  retry = (id: string) => this.request<Conversation>('POST', `/conversations/${encodeURIComponent(id)}/retry`);
}
