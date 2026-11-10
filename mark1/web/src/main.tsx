import { StrictMode, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { AppProvider, MuteProvider, type AppEnv } from './app/context';
import { ApiClient, HttpTransport, type Transport } from './api/client';
import { FakeServer } from './fake/fakeServer';
import { SessionController } from './state/controller';
import { BrowserSpeech } from './speech/speech';
import { Gallery } from './components/Gallery';
import './styles/app.css';

const mode: 'fake' | 'real' = import.meta.env.VITE_API_MODE === 'real' ? 'real' : 'fake';
const fake = mode === 'fake' ? new FakeServer() : null;
const transport: Transport = fake ?? new HttpTransport('');
const speech = new BrowserSpeech();

function makeEnv(): AppEnv {
  const controller = new SessionController({
    api: new ApiClient(transport),
    onInvalidate: () => speech.abortAll(),
  });
  return { controller, speech, mode, fake };
}

function Root() {
  const [env, setEnv] = useState(makeEnv);
  const [gen, setGen] = useState(0);
  const reset = () => {
    env.controller.dispose();
    speech.abortAll();
    setEnv(makeEnv());
    setGen((g) => g + 1);
  };
  const gallery = new URLSearchParams(window.location.search).has('gallery');
  return (
    <AppProvider env={env}>
      <MuteProvider>{gallery ? <Gallery /> : <App key={gen} onReset={reset} />}</MuteProvider>
    </AppProvider>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
