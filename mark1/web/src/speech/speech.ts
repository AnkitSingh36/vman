/**
 * Browser speech adapter (J-04). Backend accepts text only: recognised speech becomes an editable
 * transcript the user must explicitly send. No audio is uploaded by this app.
 *
 * Disclosure: depending on browser/platform, the browser vendor may process microphone audio on its
 * own servers. The consent dialog states this; typing is always available. Approved wording and the
 * target-browser matrix remain open (D08 / AR-04).
 */

export interface RecognitionHandlers {
  onInterim: (text: string) => void;
  onFinal: (text: string) => void;
  onError: (code: string) => void;
  onEnd: () => void;
}

export interface SpeechAdapter {
  readonly recognitionSupported: boolean;
  readonly synthesisSupported: boolean;
  /** Start push-to-talk; returns a function that stops listening. */
  listen(h: RecognitionHandlers): () => void;
  /** Speak authorised text only. Returns false if unsupported. */
  speak(text: string, onEnd?: () => void): boolean;
  /** Cancel queued and playing speech immediately. */
  cancel(): void;
  readonly speaking: boolean;
}

interface RecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onresult: ((e: { resultIndex: number; results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

type RecognitionCtor = new () => RecognitionLike;

export class BrowserSpeech implements SpeechAdapter {
  private ctor: RecognitionCtor | null;
  private synth: SpeechSynthesis | null;
  private active: RecognitionLike | null = null;
  private utterance: SpeechSynthesisUtterance | null = null;

  constructor(private readonly lang = 'en-US', w: Partial<Window> & Record<string, unknown> = globalThis as never) {
    this.ctor = ((w.SpeechRecognition as RecognitionCtor | undefined) ?? (w.webkitSpeechRecognition as RecognitionCtor | undefined)) ?? null;
    this.synth = (w.speechSynthesis as SpeechSynthesis | undefined) ?? null;
  }

  get recognitionSupported() {
    return this.ctor !== null;
  }
  get synthesisSupported() {
    return this.synth !== null && typeof SpeechSynthesisUtterance !== 'undefined';
  }
  get speaking() {
    return !!this.synth?.speaking;
  }

  listen(h: RecognitionHandlers): () => void {
    if (!this.ctor) {
      h.onError('unsupported');
      h.onEnd();
      return () => undefined;
    }
    this.active?.abort();
    const r = new this.ctor();
    r.lang = this.lang;
    r.interimResults = true;
    r.continuous = false;
    r.maxAlternatives = 1;
    let finalText = '';
    r.onresult = (e) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) finalText += res[0].transcript;
        else interim += res[0].transcript;
      }
      if (interim) h.onInterim((finalText + interim).trim());
      if (finalText) h.onFinal(finalText.trim());
    };
    r.onerror = (e) => h.onError(e.error || 'error');
    r.onend = () => {
      if (this.active === r) this.active = null;
      h.onEnd();
    };
    this.active = r;
    try {
      r.start();
    } catch {
      h.onError('start-failed');
      h.onEnd();
    }
    return () => {
      try {
        r.stop();
      } catch {
        /* already stopped */
      }
    };
  }

  speak(text: string, onEnd?: () => void): boolean {
    if (!this.synthesisSupported || !this.synth) return false;
    this.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = this.lang;
    u.onend = () => {
      if (this.utterance === u) this.utterance = null;
      onEnd?.();
    };
    u.onerror = u.onend;
    this.utterance = u;
    this.synth.speak(u);
    return true;
  }

  cancel(): void {
    this.utterance = null;
    try {
      this.synth?.cancel();
    } catch {
      /* ignore */
    }
  }

  /** Abort listening too (stop/offline/background). */
  abortAll(): void {
    this.cancel();
    this.active?.abort();
    this.active = null;
  }
}

/** Test/fallback adapter with no speech capability. */
export class NoSpeech implements SpeechAdapter {
  readonly recognitionSupported = false;
  readonly synthesisSupported = false;
  readonly speaking = false;
  listen(h: RecognitionHandlers) {
    h.onError('unsupported');
    h.onEnd();
    return () => undefined;
  }
  speak() {
    return false;
  }
  cancel() {}
}
