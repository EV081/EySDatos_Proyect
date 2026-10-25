// Prueba de extremo a extremo: levanta client.dev (backend real con directorio y canal en memoria), sirve
// el sitio exportado y maneja dos pestañas de Chromium (Alice y Bob) por el protocolo de depuración.
//   npm run build && npm run e2e
import { spawn } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const shots = process.env.SHOTS_DIR ?? join(tmpdir(), 'e2ee-shots');
mkdirSync(shots, { recursive: true });
const ALICE = '111111111111111111', BOB = '222222222222222222';
const PASS_A = 'contraseña-de-alice-1', PASS_B = 'contraseña-de-bob-2';
const procs = [];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let passed = 0;

function start(cmd, args, opts = {}) {
  const p = spawn(cmd, args, { stdio: ['ignore', 'pipe', 'pipe'], ...opts });
  procs.push(p);
  return p;
}
function check(name, ok, extra = '') {
  if (!ok) throw new Error(`FALLÓ: ${name} ${extra}`);
  passed++;
  console.log(`  ✔ ${name}`);
}
async function until(fn, what, ms = 8000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    try { const v = await fn(); if (v) return v; } catch { /* aún no */ }
    await sleep(100);
  }
  throw new Error(`Tiempo agotado esperando: ${what}`);
}

class Page {
  constructor(ws, name) { this.ws = ws; this.name = name; this.id = 0; this.pending = new Map(); this.dialogs = [];
    ws.addEventListener('message', (e) => { const m = JSON.parse(e.data); if (m.id && this.pending.has(m.id)) { this.pending.get(m.id)(m); this.pending.delete(m.id); } else if (m.method === 'Runtime.exceptionThrown') console.log(`  [${name}] excepción:`, m.params.exceptionDetails.text, m.params.exceptionDetails.exception?.description ?? ''); }); }
  send(method, params = {}) { const id = ++this.id; this.ws.send(JSON.stringify({ id, method, params })); return new Promise((res, rej) => { this.pending.set(id, (m) => (m.error ? rej(new Error(m.error.message)) : res(m.result))); }); }
  async eval(expr) { const r = await this.send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true }); if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? 'error de evaluación'); return r.result.value; }
  text() { return this.eval('document.body.innerText'); }
  has(text) { return this.text().then((t) => t.includes(text)); }
  waitText(text, ms) { return until(() => this.has(text), `"${text}" en ${this.name}`, ms); }
  click(sel) { return this.eval(`(() => { const el = document.querySelector(${JSON.stringify(sel)}); if (!el) throw new Error('no existe ${sel}'); el.click(); return true; })()`); }
  clickText(text, scope = 'button') { return this.eval(`(() => { const el = [...document.querySelectorAll(${JSON.stringify(scope)})].find((b) => b.innerText.includes(${JSON.stringify(text)})); if (!el) throw new Error('no hay ${scope} con ${text}'); el.click(); return true; })()`); }
  async type(sel, text) { await this.eval(`(() => { const el = document.querySelector(${JSON.stringify(sel)}); if (!el) throw new Error('no existe ${sel}'); el.focus(); el.select?.(); return true; })()`); await this.send('Input.insertText', { text }); }
  async key(key) { for (const type of ['keyDown', 'keyUp']) await this.send('Input.dispatchKeyEvent', { type, key, code: key, windowsVirtualKeyCode: key === 'Enter' ? 13 : 0, text: key === 'Enter' ? '\r' : undefined }); }
  async shot(name) { const r = await this.send('Page.captureScreenshot', { format: 'png' }); const f = join(shots, `${name}.png`); writeFileSync(f, Buffer.from(r.data, 'base64')); return f; }
}

async function cleanup() { for (const p of procs) { try { p.kill('SIGKILL'); } catch { /* ya terminó */ } } }
process.on('exit', () => procs.forEach((p) => p.kill('SIGKILL')));

try {
  console.log('Iniciando backend de desarrollo, servidor estático y Chromium…');
  const dev = start(join(root, '.venv/bin/python'), ['-m', 'client.dev'], { cwd: root });
  start('node', [join(root, 'frontend/scripts/serve.mjs')], { cwd: join(root, 'frontend') });
  const debugPort = 9333;
  start('chromium', ['--headless=new', '--no-sandbox', '--disable-gpu', `--remote-debugging-port=${debugPort}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), 'e2ee-chrome-'))}`, '--window-size=1200,800', 'about:blank']);
  await until(async () => (await fetch('http://127.0.0.1:8001/health')).ok && (await fetch('http://127.0.0.1:8002/health')).ok && (await fetch('http://127.0.0.1:5173/')).ok, 'servicios', 15000);
  await until(async () => (await fetch(`http://127.0.0.1:${debugPort}/json/version`)).ok, 'Chromium', 15000);

  const open = async (name, api) => {
    const tgt = await (await fetch(`http://127.0.0.1:${debugPort}/json/new?${encodeURIComponent(`http://127.0.0.1:5173/?api=http://127.0.0.1:${api}&token=dev-token`)}`, { method: 'PUT' })).json();
    const ws = new WebSocket(tgt.webSocketDebuggerUrl);
    await new Promise((r) => ws.addEventListener('open', r));
    const page = new Page(ws, name);
    await page.send('Runtime.enable'); await page.send('Page.enable');
    await page.send('Emulation.setDeviceMetricsOverride', { width: 1100, height: 760, deviceScaleFactor: 1, mobile: false });
    return page;
  };
  const alice = await open('Alice', 8001), bob = await open('Bob', 8002);

  console.log('Identidad');
  for (const [page, id, pass] of [[alice, ALICE, PASS_A], [bob, BOB, PASS_B]]) {
    await page.waitText('Crear identidad');
    await page.type('input[inputmode="numeric"]', id);
    await page.eval(`document.querySelectorAll('input[type=password]')[0].focus()`); await page.send('Input.insertText', { text: pass });
    await page.eval(`document.querySelectorAll('input[type=password]')[1].focus()`); await page.send('Input.insertText', { text: pass });
    await page.clickText('Crear identidad');
    await page.waitText('CONTACTOS');
  }
  check('Alice y Bob crean su identidad y llegan a la aplicación', await alice.has('CONTACTOS') && await bob.has('CONTACTOS'));
  check('el token no quedó en la URL', !(await alice.eval('location.href')).includes('token'));

  console.log('Contactos');
  for (const [page, other] of [[alice, BOB], [bob, ALICE]]) {
    await page.clickText('+ Agregar contacto');
    await page.type('input[placeholder="ID de Discord"]', other);
    await page.clickText('Agregar', 'form.add button');
    await page.waitText('Sin mensajes');
  }
  check('cada uno ve al otro en su lista', await alice.has(BOB) && await bob.has(ALICE));

  console.log('Mensajes');
  await alice.clickText(BOB, 'li.contact');
  await bob.clickText(ALICE, 'li.contact');
  await alice.type('textarea', 'Hola Bob, este mensaje viaja cifrado');
  await alice.key('Enter');
  await bob.waitText('Hola Bob, este mensaje viaja cifrado', 15000);
  check('Bob ve descifrado el mensaje de Alice (handshake automático)', true);
  await alice.waitText('Cifrado AES-256-GCM', 10000);
  check('Alice ve su mensaje como enviado y cifrado', true);
  check('el candado de sesión activa aparece en ambos', await alice.has('Cifrado E2EE') && await bob.has('Cifrado E2EE'));
  await bob.type('textarea', 'Recibido, Alice');
  await bob.key('Enter');
  await alice.waitText('Recibido, Alice', 10000);
  check('la respuesta de Bob llega a Alice', true);

  console.log('Seguridad de la interfaz');
  const payload = '<img src=x onerror="window.__pwned=1"> <b>negrita</b>';
  await alice.type('textarea', payload);
  await alice.key('Enter');
  await bob.waitText('negrita', 10000);
  await sleep(300);
  check('un mensaje con HTML se muestra como texto literal', await bob.has(payload));
  check('no se creó ningún elemento ni se ejecutó código', await bob.eval(`!document.querySelector('.messages img, .messages b') && window.__pwned === undefined`));

  console.log('Verificación fuera de banda');
  await alice.clickText('Verificar', '.chat-head button');
  await alice.waitText('Huella que te dicta tu contacto');
  const readFp = (page) => until(async () => { const t = await page.eval(`document.querySelector('[data-testid=verify-fp]').innerText`); return /\d{5}/.test(t) ? t : null; }, `huella en ${page.name}`);
  const fpAlice = await readFp(alice);
  await bob.clickText('Verificar', '.chat-head button');
  await bob.waitText('Huella que te dicta tu contacto');
  const fpBob = await readFp(bob);
  check('ambos ven la misma huella de 60 dígitos', fpAlice === fpBob && fpAlice.replace(/\D/g, '').length === 60, fpAlice);
  await alice.type('dialog input', '00000 11111 22222');
  await alice.clickText('Confirmar', 'dialog button');
  await alice.waitText('no coincide');
  check('una huella incorrecta se rechaza y no verifica', await alice.has('no coincide') && !(await alice.has('✓ Verificado')));
  await alice.type('dialog input', fpBob);
  await alice.clickText('Confirmar', 'dialog button');
  await alice.waitText('✓ Verificado');
  check('con la huella correcta el contacto queda verificado', true);
  await alice.shot('alice-verificado');

  console.log('Bloqueo');
  await alice.clickText('Gestión de identidad', 'button.identity');
  await alice.waitText('Llave pública de firma');
  await alice.clickText('Bloquear', 'dialog button');
  await alice.waitText('Ingresa tu contraseña maestra');
  check('al bloquear se pide la contraseña y no se ve ninguna conversación', !(await alice.has('Recibido, Alice')));
  await alice.eval(`document.querySelector('input[type=password]').focus()`); await alice.send('Input.insertText', { text: 'incorrecta-123' });
  await alice.clickText('Desbloquear');
  await alice.waitText('Contraseña incorrecta');
  check('una contraseña incorrecta no desbloquea', true);
  await alice.eval(`document.querySelector('input[type=password]').select()`); await alice.send('Input.insertText', { text: PASS_A });
  await alice.clickText('Desbloquear');
  await alice.waitText('CONTACTOS');
  check('con la contraseña correcta vuelve a la aplicación', true);

  await bob.shot('bob-conversacion');
  console.log(`\n${passed} comprobaciones pasaron. Capturas en ${shots}`);
  await cleanup();
  process.exit(0);
} catch (err) {
  console.error('\n' + err.message);
  await cleanup();
  process.exit(1);
}
