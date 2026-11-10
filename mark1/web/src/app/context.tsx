import { createContext, useContext, useEffect, useState, useSyncExternalStore, type ReactNode } from 'react';
import type { SessionController, ControllerState } from '../state/controller';
import type { SpeechAdapter } from '../speech/speech';
import type { FakeServer } from '../fake/fakeServer';

export interface AppEnv {
  controller: SessionController;
  speech: SpeechAdapter;
  mode: 'fake' | 'real';
  fake: FakeServer | null;
  /** Read-only rendering (fixture gallery): no commands are sent. */
  readOnly?: boolean;
}

const Ctx = createContext<AppEnv | null>(null);

export function AppProvider({ env, children }: { env: AppEnv; children: ReactNode }) {
  return <Ctx.Provider value={env}>{children}</Ctx.Provider>;
}

export function useEnv(): AppEnv {
  const v = useContext(Ctx);
  if (!v) throw new Error('AppProvider missing');
  return v;
}

export function useControllerState(): ControllerState {
  const { controller } = useEnv();
  return useSyncExternalStore(controller.subscribe, controller.getState, controller.getState);
}

/** Re-render periodically so lease expiry is reflected even without new server data. */
export function useNow(intervalMs = 250): number {
  const { controller } = useEnv();
  const [now, setNow] = useState(() => controller.now());
  useEffect(() => {
    const h = setInterval(() => setNow(controller.now()), intervalMs);
    return () => clearInterval(h);
  }, [controller, intervalMs]);
  return now;
}

/** Speech mute is a per-page preference (memory only). */
const MuteCtx = createContext<{ muted: boolean; setMuted: (m: boolean) => void }>({ muted: false, setMuted: () => undefined });
export function MuteProvider({ children }: { children: ReactNode }) {
  const [muted, setMuted] = useState(false);
  return <MuteCtx.Provider value={{ muted, setMuted }}>{children}</MuteCtx.Provider>;
}
export const useMute = () => useContext(MuteCtx);
