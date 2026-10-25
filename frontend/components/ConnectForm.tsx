'use client';
import { useState, type FormEvent } from 'react';

export function ConnectForm({ onConnect }: { onConnect: (base: string, token: string) => void }) {
  const [base, setBase] = useState('http://127.0.0.1:8001');
  const [token, setToken] = useState('');

  const submit = (e: FormEvent) => {
    e.preventDefault();
    onConnect(base, token);
  };

  return (
    <section className="card center">
      <h1>Conectar con el cliente local</h1>
      <p className="muted">El cliente local corre en tu equipo (127.0.0.1). El token se muestra al iniciarlo.</p>
      <form onSubmit={submit}>
        <label>
          Dirección
          <input value={base} onChange={(e) => setBase(e.target.value)} required />
        </label>
        <label>
          Token
          <input type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} required />
        </label>
        <button className="primary">Conectar</button>
      </form>
    </section>
  );
}
