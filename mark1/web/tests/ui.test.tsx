import examples from '@contracts/examples.json';
import allFixtures from '@contracts/all-fixtures.json';
import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { App } from '../src/App';
import { AppProvider, MuteProvider, type AppEnv } from '../src/app/context';
import { CutawayDiagram } from '../src/components/CutawayDiagram';
import { SessionScreen } from '../src/components/SessionScreen';
import { ReadAloud } from '../src/components/common';
import { _resetConsentForTests } from '../src/components/ChatPanel';
import type { RecognitionHandlers, SpeechAdapter } from '../src/speech/speech';
import type { ExplanationInteraction, Session } from '../src/api/types';
import { setup } from './helpers';

class FakeSpeech implements SpeechAdapter {
  recognitionSupported = true;
  synthesisSupported = true;
  speaking = false;
  spoken: string[] = [];
  cancels = 0;
  handlers: RecognitionHandlers | null = null;
  listen(h: RecognitionHandlers) {
    this.handlers = h;
    return () => h.onEnd();
  }
  speak(t: string) {
    this.spoken.push(t);
    this.speaking = true;
    return true;
  }
  cancel() {
    this.cancels++;
    this.speaking = false;
  }
}

function renderWith(env: Partial<AppEnv> & { controller: AppEnv['controller'] }, ui: JSX.Element) {
  const full: AppEnv = { speech: new FakeSpeech(), mode: 'fake', fake: null, ...env };
  return { env: full, ...render(<AppProvider env={full}><MuteProvider>{ui}</MuteProvider></AppProvider>) };
}

const ex = examples as unknown as Record<string, Session>;
const fixtures = allFixtures as unknown as { sessions: Record<string, Session>; session_variants: Record<string, Session> };

beforeEach(() => {
  _resetConsentForTests();
  window.history.replaceState(null, '', '/');
});

describe('cutaway renderer (J-05)', () => {
  it('renders authored nodes, version/source and a labelled SUSPECTED highlight', () => {
    const it = ex.explanation_session.interaction as ExplanationInteraction;
    const { controller } = setup();
    const { container } = renderWith({ controller }, <CutawayDiagram diagram={it.diagram} highlights={it.highlights} />);
    expect(container.querySelectorAll('[data-node]')).toHaveLength(3);
    expect(container.querySelectorAll('[data-edge]')).toHaveLength(2);
    expect(container.querySelector('[data-node="INPUT"]')!.getAttribute('data-highlight')).toBe('SUSPECTED');
    expect(screen.getByText(/not an internal camera observation/i)).toBeInTheDocument();
    expect(screen.getByText(/DEMO-POWER-FLOW v1/)).toBeInTheDocument();
    expect(screen.getByText(/Suspected — advisory, cause unconfirmed/)).toBeInTheDocument();
  });

  it('renders labels as text, never markup', () => {
    const it = JSON.parse(JSON.stringify(ex.explanation_session.interaction)) as ExplanationInteraction;
    it.diagram!.nodes[0].label = '<img src=x onerror=alert(1)>';
    const { controller } = setup();
    const { container } = renderWith({ controller }, <CutawayDiagram diagram={it.diagram} highlights={it.highlights} />);
    expect(container.querySelector('img')).toBeNull();
    expect(container.textContent).toContain('<img src=x onerror=alert(1)>');
  });

  it('missing diagram shows explicit unavailable fallback', () => {
    const { controller } = setup();
    renderWith({ controller }, <SessionScreen session={fixtures.session_variants.MISSING_DIAGRAM} hidden={null} busy={false} history={[]} onNew={() => undefined} />);
    expect(screen.getByTestId('diagram-unavailable')).toBeInTheDocument();
    expect(screen.queryByTestId('diagram')).toBeNull();
    expect(screen.getByText(/cause unconfirmed/i, { selector: '.badge' })).toBeInTheDocument();
  });
});

describe('state rendering', () => {
  it.each(Object.keys(fixtures.sessions))('fixture %s renders without crashing and with the right panel', (k) => {
    const { controller } = setup();
    renderWith({ controller, readOnly: true }, <SessionScreen session={fixtures.sessions[k]} hidden={null} busy={false} history={[]} onNew={() => undefined} />);
    const s = fixtures.sessions[k];
    if (s.status === 'READY') expect(screen.getByText('Approved check')).toBeInTheDocument();
    if (s.status === 'AWAITING_VIEW') expect(screen.getByText(/Show a view|Show the label/)).toBeInTheDocument();
    if (s.status === 'AWAITING_ANSWER') expect(screen.getByText('Question')).toBeInTheDocument();
    if (s.status === 'EXPLAINING') expect(screen.getByTestId('diagram')).toBeInTheDocument();
    if (s.status === 'RECORD_PENDING') expect(screen.getByTestId('record-pending')).toHaveTextContent('Not yet saved');
    if (s.status === 'COMPLETED') expect(screen.getByText(/not a verified repair/)).toBeInTheDocument();
  });

  it('hidden guidance removes text, options and highlights but keeps safety visible', () => {
    const { controller } = setup();
    renderWith({ controller }, <SessionScreen session={ex.explanation_session} hidden="EXPIRED" busy={false} history={[]} onNew={() => undefined} />);
    expect(screen.queryByTestId('guidance-text')).toBeNull();
    expect(screen.queryByTestId('diagram')).toBeNull();
    expect(screen.getByTestId('guidance-hidden')).toHaveTextContent(/expired/i);
    expect(screen.getByLabelText('Safety')).toBeInTheDocument();
  });
});

describe('speech (J-04)', () => {
  it('reads only the given authorized text and cancels when hidden or context changes', async () => {
    const speech = new FakeSpeech();
    const { controller } = setup();
    const { rerender } = renderWith({ controller, speech }, <ReadAloud text="Approved text" guidanceKey="k1" hidden={false} />);
    await userEvent.click(screen.getByRole('button', { name: 'Read aloud' }));
    expect(speech.spoken).toEqual(['Approved text']);
    const before = speech.cancels;
    rerender(<AppProvider env={{ controller, speech, mode: 'fake', fake: null }}><MuteProvider><ReadAloud text="Approved text" guidanceKey="k1" hidden={true} /></MuteProvider></AppProvider>);
    expect(speech.cancels).toBeGreaterThan(before);
    expect(screen.getByRole('button', { name: 'Read aloud' })).toBeDisabled();
  });

  it('voice needs consent, yields an editable transcript, and is sent only on explicit Send as VOICE_TRANSCRIPT', async () => {
    const speech = new FakeSpeech();
    const { controller, rec } = setup();
    await controller.start();
    renderWith({ controller, speech }, <App onReset={() => undefined} />);
    await userEvent.click(screen.getByRole('button', { name: 'Talk' }));
    expect(screen.getByRole('dialog')).toHaveTextContent(/browser vendor/);
    await userEvent.click(screen.getByRole('button', { name: 'Allow voice input' }));
    act(() => speech.handlers!.onFinal('display stays dark'));
    const box = screen.getByLabelText(/Describe what you see/) as HTMLTextAreaElement;
    expect(box.value).toBe('display stays dark');
    expect(rec.posts('messages')).toHaveLength(0); // nothing sent yet
    await userEvent.type(box, ' (fictional)');
    await userEvent.click(screen.getByRole('button', { name: 'Send' }));
    const sent = rec.posts('messages');
    expect(sent).toHaveLength(1);
    expect(sent[0].json).toMatchObject({ text: 'display stays dark (fictional)', channel: 'VOICE_TRANSCRIPT', human_confirmed: true });
    expect(await screen.findByText(/not a confirmed observation/)).toBeInTheDocument();
  });

  it('unsupported browser: no mic button, typing still works', async () => {
    const speech = new FakeSpeech();
    speech.recognitionSupported = false;
    speech.synthesisSupported = false;
    const { controller } = setup();
    await controller.start();
    renderWith({ controller, speech }, <App onReset={() => undefined} />);
    expect(screen.queryByRole('button', { name: 'Talk' })).toBeNull();
    expect(screen.getByText(/Voice input is not supported/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Describe what you see/)).toBeEnabled();
  });
});

describe('phone journey through the UI (J-02/J-03/J-07)', () => {
  it('reload with an unknown session id returns to start with a notice', async () => {
    window.history.replaceState(null, '', '/#s=missing-session');
    const { controller } = setup();
    renderWith({ controller }, <App onReset={() => undefined} />);
    expect(await screen.findByText(/session is not available/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Start: device has no power/ })).toBeInTheDocument();
  });

  it('identity requires explicit label confirmation; preflight and Stop are always available', async () => {
    const { controller, rec } = setup();
    renderWith({ controller }, <App onReset={() => undefined} />);
    await userEvent.click(screen.getByRole('button', { name: /Start: device has no power/ }));
    await userEvent.type(await screen.findByLabelText('Label text'), 'DEMO-LAPTOP');
    await userEvent.click(screen.getByRole('button', { name: 'Look up' }));
    const confirm = await screen.findByRole('button', { name: 'Confirm identity' });
    expect(confirm).toBeDisabled();
    await userEvent.click(screen.getByRole('radio', { name: /DEMO-LAPTOP/ }));
    expect(confirm).toBeDisabled(); // still needs the physical-label confirmation
    await userEvent.click(screen.getByRole('checkbox', { name: /compared the model/ }));
    await userEvent.click(confirm);
    expect(rec.posts('identity-confirmation')[0].json).toMatchObject({ model_id: 'DEMO-LAPTOP', configuration_id: 'DEMO-C1', human_confirmed: true });

    // Preflight check
    expect(await screen.findByText('Approved check')).toBeInTheDocument();
    expect(screen.getByTestId('guidance-text')).toHaveTextContent(/preflight/i);
    await userEvent.click(screen.getByRole('radio', { name: 'CLEAR' }));
    const save = screen.getByRole('button', { name: 'Save observation' });
    expect(save).toBeDisabled();
    await userEvent.click(screen.getByRole('checkbox', { name: /made this observation myself/ }));
    await userEvent.click(save);
    expect(await screen.findByText('Show a view')).toBeInTheDocument();

    // Unavailable view, then question
    await userEvent.click(screen.getByRole('button', { name: "Can't show this view" }));
    expect(await screen.findByText('Show a view')).toBeInTheDocument();

    // Stop is available and takes effect locally immediately
    const stopbar = screen.getByRole('region', { name: 'Stop controls' });
    await userEvent.click(within(stopbar).getByRole('button', { name: 'Stop' }));
    expect(await screen.findByText(/Escalated/, { selector: 'h2' })).toBeInTheDocument();
    expect(screen.queryByTestId('guidance-text')).toBeNull();
    expect(rec.posts('stop')[0].json).toMatchObject({ reason_code: 'USER_STOP' });
    expect(await screen.findByText(/STOP_RECORDED/)).toBeInTheDocument();
  });

  it('an expired lease hides the active prompt in the live app', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const { controller, fake } = setup();
      await controller.start();
      await controller.submit('identity-candidates', (s) => ({ expected_revision: s.revision, manual_label: 'DEMO-LAPTOP' }));
      await controller.submit('identity-confirmation', (s) => ({ expected_revision: s.revision, model_id: 'DEMO-LAPTOP', configuration_id: 'DEMO-C1', human_confirmed: true }));
      fake.faults.freezeLeases = true;
      renderWith({ controller }, <App onReset={() => undefined} />);
      expect(screen.getByTestId('guidance-text')).toBeInTheDocument();
      await act(async () => {
        vi.advanceTimersByTime(16_000);
      });
      expect(screen.queryByTestId('guidance-text')).toBeNull();
      expect(screen.getByTestId('guidance-hidden')).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
