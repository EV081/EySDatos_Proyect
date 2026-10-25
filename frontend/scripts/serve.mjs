// Servidor estático mínimo para el sitio exportado (out/). Solo escucha en 127.0.0.1.
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join, normalize, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('../out', import.meta.url)));
const port = Number(process.env.PORT ?? 5173);
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.txt': 'text/plain', '.woff2': 'font/woff2' };
const headers = { 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY', 'Cache-Control': 'no-store' };

const isFile = async (path) => (await stat(path).catch(() => null))?.isFile() ?? false;

// /privacidad -> privacidad.html; /carpeta/ -> carpeta/index.html
async function locate(pathname) {
  const base = resolve(join(root, normalize(decodeURIComponent(pathname))));
  if (base !== root && !base.startsWith(root + '/')) return { status: 403 };
  for (const candidate of [base, `${base}.html`, join(base, 'index.html')]) {
    if (await isFile(candidate)) return { file: candidate };
  }
  return { status: 404 };
}

createServer(async (req, res) => {
  try {
    const { file, status } = await locate(new URL(req.url ?? '/', 'http://localhost').pathname);
    if (!file) {
      res.writeHead(status, headers);
      return res.end(status === 403 ? 'Prohibido' : 'No encontrado');
    }
    const body = await readFile(file); // se lee antes de escribir las cabeceras
    res.writeHead(200, { ...headers, 'Content-Type': types[extname(file)] ?? 'application/octet-stream' });
    res.end(body);
  } catch {
    if (!res.headersSent) res.writeHead(400, headers);
    res.end('Solicitud inválida');
  }
}).listen(port, '127.0.0.1', () => console.log(`Frontend en http://127.0.0.1:${port}`));
