import { useState } from 'react';

/** Local demo credential only: never saved to browser storage, URLs or build variables. */
export function BackendConnection({ onConnect }: { onConnect: (token: string) => void }) {
  const [token, setToken] = useState('');
  return (
    <main className="app">
      <h1>Mark-1</h1>
      <section className="panel">
        <h2>Connect to the demo backend</h2>
        <p>Use the demo bearer token printed by <code>python -m mark1.server init</code>.</p>
        <p>Keep it private. It stays in memory until this page is reloaded. The server verifies it on each request.</p>
        <form onSubmit={(event) => {
          event.preventDefault();
          const value = token.trim();
          if (!value) return;
          setToken('');
          onConnect(value);
        }}>
          <label htmlFor="demo-token">Demo bearer token</label>
          <input id="demo-token" type="password" autoComplete="off" spellCheck={false}
            value={token} onChange={(event) => setToken(event.target.value)} required />
          <button type="submit" className="primary" disabled={!token.trim()}>Use demo token</button>
        </form>
        <p className="small muted">Synthetic content only. The deterministic backend does not interpret photos or diagnose real devices.</p>
      </section>
    </main>
  );
}
