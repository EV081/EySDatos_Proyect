// Solo http://127.0.0.1 o http://localhost: el token de la API local nunca debe viajar a otro destino.
export function isLocal(base: string): boolean {
  try {
    const u = new URL(base);
    // Sin credenciales incrustadas (user@host): confunden a quien lee la dirección.
    return u.protocol === 'http:' && !u.username && !u.password && (u.hostname === '127.0.0.1' || u.hostname === 'localhost');
  } catch {
    return false;
  }
}
