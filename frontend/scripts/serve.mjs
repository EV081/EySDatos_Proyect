// Servidor estático mínimo para el sitio exportado (out/). Solo escucha en 127.0.0.1.
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join, normalize, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('../out', import.meta.url)));
const port = Number(process.env.PORT ?? 5173);
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.txt': 'text/plain', '.woff2': 'font/woff2' };

createServer(async (req, res) => {
  const headers = { 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY', 'Cache-Control': 'no-store' };
  try {
    const url = new URL(req.url ?? '/', 'http://localhost');
    let file = resolve(join(root, normalize(decodeURIComponent(url.pathname))));
    if (file !== root && !file.startsWith(root + '/')) throw Object.assign(new Error('fuera de la raíz'), { code: 'EACCES' });
    if ((await stat(file)).isDirectory()) file = join(file, 'index.html');
    res.writeHead(200, { ...headers, 'Content-Type': types[extname(file)] ?? 'application/octet-stream' });
    res.end(await readFile(file));
  } catch (err) {
    res.writeHead(err.code === 'EACCES' ? 403 : 404, headers);
    res.end('No encontrado');
  }
}).listen(port, '127.0.0.1', () => console.log(`Frontend en http://127.0.0.1:${port}`));
