// J-07 browser evidence: drives the real app (fake backend mode) at phone size in an installed
// Chromium-family browser and saves a screenshot per step to e2e/out/.
//
//   npm run dev            (in another terminal)
//   npm run e2e            (E2E_URL / E2E_CHANNEL=msedge|chrome to override)
//
// No browser is downloaded (playwright-core). Fictional data only.
import { chromium } from 'playwright-core';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const out = path.join(here, 'out');
mkdirSync(out, { recursive: true });
const url = process.env.E2E_URL ?? 'http://localhost:5173/';
const channel = process.env.E2E_CHANNEL ?? (process.platform === 'win32' ? 'msedge' : 'chrome');
const frame = path.join(here, 'fictional-frame.png');
const real = process.env.E2E_REAL === '1';

const browser = await chromium.launch({ channel, headless: process.env.E2E_HEADED ? false : true });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
let n = 0;
const shot = (name) => page.screenshot({ path: path.join(out, `${String(++n).padStart(2, '0')}-${name}.png`), fullPage: true });
const status = () => page.locator('[data-testid=status]').textContent().catch(() => '-');
const step = async (label, fn) => {
  await fn();
  console.log(`ok  ${label.padEnd(34)} status=${await status()}`);
};

try {
  await page.goto(url);
  if (real) {
    if (!process.env.E2E_TOKEN) throw new Error('The real-backend runner must supply a temporary token.');
    await step('enter demo token', async () => {
      await page.getByLabel('Demo bearer token').fill(process.env.E2E_TOKEN);
      await page.getByRole('button', { name: 'Use demo token' }).click();
    });
  }
  await step('start session', () => page.getByRole('button', { name: /Start: device has no power/ }).click());
  await step(real ? 'look up fictional label' : 'send label photo', async () => {
    if (real) {
      await page.getByLabel('Label text').fill('DEMO-LAPTOP');
      await page.getByRole('button', { name: 'Look up', exact: true }).click();
    } else {
      await page.locator('input[type=file]').first().setInputFiles(frame);
      await page.getByRole('button', { name: 'Send selected photo' }).click();
    }
    await page.getByRole('button', { name: 'Confirm identity' }).waitFor();
  });
  await shot('identity-candidates');
  await step('confirm identity against label', async () => {
    await page.getByRole('radio', { name: /DEMO-LAPTOP/ }).check();
    await page.getByRole('checkbox', { name: /compared the model/ }).check();
    await page.getByRole('button', { name: 'Confirm identity' }).click();
    await page.getByText('Approved check').waitFor();
  });
  await shot('preflight');
  await step('preflight CLEAR', async () => {
    await page.getByRole('radio', { name: 'CLEAR' }).check();
    await page.getByRole('checkbox', { name: /made this observation myself/ }).check();
    await page.getByRole('button', { name: 'Save observation' }).click();
    await page.getByText('Show a view').waitFor();
  });
  await shot('view-request');
  await step('send selected view snapshot', async () => {
    await page.locator('input[type=file]').first().setInputFiles(frame);
    await page.getByRole('button', { name: 'Send selected snapshot' }).click();
    await page.getByRole('heading', { name: 'Question' }).waitFor();
  });
  await step('chat message (human report)', async () => {
    await page.getByLabel(/Describe what you see/).fill('Fictional device: the screen stays dark.');
    await page.getByRole('button', { name: 'Send', exact: true }).click();
    await page.getByText('Saved', { exact: true }).waitFor();
    await page.getByRole('heading', { name: 'Question' }).waitFor();
  });
  await shot('question');
  await step('answer NO', async () => {
    await page.getByRole('radio', { name: 'NO' }).check();
    await page.getByRole('button', { name: 'Submit answer' }).click();
    await page.getByRole('radio', { name: 'OFF' }).waitFor();
  });
  await step('indicator OFF', async () => {
    await page.getByRole('radio', { name: 'OFF' }).check();
    await page.getByRole('checkbox', { name: /made this observation myself/ }).check();
    await page.getByRole('button', { name: 'Save observation' }).click();
    await page.getByTestId('diagram').waitFor();
  });
  await shot('explanation-cutaway');
  await step('offline hides guidance', async () => {
    await ctx.setOffline(true);
    await page.getByTestId('guidance-hidden').waitFor();
  });
  await shot('offline-hidden');
  await step('online -> refreshed guidance', async () => {
    await ctx.setOffline(false);
    await page.getByTestId('diagram').waitFor();
  });
  await step('acknowledge -> escalated summary', async () => {
    await page.getByRole('button', { name: 'Continue' }).click();
    await page.getByText('History (historical record — not instructions)').waitFor();
  });
  await shot('summary');
  console.log(`history events: ${await page.locator('.events li').count()}`);
  if (real) {
    const sid = new URLSearchParams(new URL(page.url()).hash.slice(1)).get('s');
    const headers = { Authorization: `Bearer ${process.env.E2E_TOKEN}` };
    const current = await ctx.request.get(`${url}v2/sessions/${sid}`, { headers });
    const session = await current.json();
    if (session.status !== 'ESCALATED') throw new Error('Final backend state was not persisted.');
    const history = await ctx.request.get(`${url}v2/sessions/${sid}/events`, { headers });
    const { events } = await history.json();
    for (const type of ['IMAGES', 'ANSWERS', 'OBSERVATIONS', 'MESSAGES', 'EXPLANATION-ACKS']) {
      if (!events.some((event) => event.event_type === type)) throw new Error(`Missing durable event: ${type}`);
    }
    await page.reload();
    await page.getByLabel('Demo bearer token').waitFor();
    await page.getByLabel('Demo bearer token').fill(process.env.E2E_TOKEN);
    await page.getByRole('button', { name: 'Use demo token' }).click();
    await page.getByText('History (historical record — not instructions)').waitFor();
    console.log('Real backend: durable events and authenticated reload/resume verified.');
  }
  console.log(errors.length ? `console errors: ${errors.join(' | ')}` : 'console errors: none');
  console.log(`screenshots: ${out}`);
  if (errors.length) process.exitCode = 1;
} catch (e) {
  await shot('failure').catch(() => undefined);
  console.error('E2E FAILED:', e);
  process.exitCode = 1;
} finally {
  await browser.close();
}
