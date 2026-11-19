// Starts isolated local services, issues an ephemeral credential, then exercises the phone UI.
// No provider, real vault, customer image or existing demo database is used.
import { spawn, execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { once } from 'node:events';

const web = fileURLToPath(new URL('..', import.meta.url));
const project = path.resolve(web, '..');
const python = process.env.MARK1_PYTHON ?? path.join(project, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const temp = mkdtempSync(path.join(tmpdir(), 'mark1-web-integration-'));
const env = { ...process.env, MARK1_MODE: 'demo', MARK1_DB: path.join(temp, 'demo.sqlite') };
const backendPort = process.env.E2E_BACKEND_PORT ?? '18761';
const webPort = process.env.E2E_WEB_PORT ?? '15173';
const backend = `http://127.0.0.1:${backendPort}`;
const url = `http://127.0.0.1:${webPort}/`;
const children = [];

function launch(command, args, cwd, childEnv) {
  const child = spawn(command, args, { cwd, env: childEnv, windowsHide: true, stdio: 'ignore' });
  child.on('error', () => {});
  children.push(child);
  return child;
}

async function ready(address, child) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (!child.pid || child.exitCode !== null) throw new Error('A test server could not start. Check dependencies and test ports.');
    try {
      if ((await fetch(address, { signal: AbortSignal.timeout(1000) })).ok) return;
    } catch { /* starting */ }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error('Timed out waiting for a local test server.');
}

try {
  console.log('Preparing temporary synthetic database.');
  // Capture the token; never print it or place it in a VITE_* build variable.
  const token = execFileSync(python, ['-c', 'from mark1.server.config import Settings; from mark1.server.service import Service; print(Service(Settings.from_env()).store.issue_token())'],
    { cwd: project, env, encoding: 'utf8', windowsHide: true, timeout: 30_000 }).trim();
  console.log('Starting FastAPI on loopback.');
  const api = launch(python, ['-m', 'uvicorn', 'mark1.server.app:create_app', '--factory', '--host', '127.0.0.1', '--port', backendPort, '--workers', '1'], project, env);
  await ready(`${backend}/health`, api);
  console.log('Starting Vite with the real API proxy.');
  const site = launch(process.execPath, ['node_modules/vite/bin/vite.js', '--mode', 'real', '--host', '127.0.0.1', '--port', webPort, '--strictPort'], web,
    { ...env, MARK1_BACKEND_URL: backend, VITE_API_MODE: 'real' });
  await ready(url, site);
  console.log('Running authenticated browser journey.');
  if ((await fetch(`${url}v2/sessions/missing`)).status !== 401) throw new Error('Unauthenticated API access was not rejected.');
  const journey = spawn(process.execPath, ['e2e/journey.mjs'], {
    cwd: web, env: { ...env, E2E_REAL: '1', E2E_URL: url, E2E_TOKEN: token }, windowsHide: true, stdio: 'inherit',
  });
  children.push(journey);
  const [code] = await once(journey, 'exit');
  process.exitCode = code ?? 1;
} finally {
  for (const child of children.reverse()) {
    if (child.pid && child.exitCode === null) {
      const stopped = once(child, 'exit');
      child.kill();
      await stopped;
    }
  }
  if (path.dirname(path.resolve(temp)) !== path.resolve(tmpdir()) || !path.basename(temp).startsWith('mark1-web-integration-')) {
    throw new Error('Refusing to remove a directory outside the integration temporary root.');
  }
  rmSync(temp, { recursive: true, force: true });
}
