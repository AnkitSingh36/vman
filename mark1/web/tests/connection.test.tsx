import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { BackendConnection } from '../src/components/BackendConnection';
import { ApiClient, HttpTransport } from '../src/api/client';

afterEach(() => vi.unstubAllGlobals());

describe('real backend connection', () => {
  it('requires an explicit token and clears the masked input after submission', async () => {
    const connect = vi.fn();
    render(<BackendConnection onConnect={connect} />);
    const user = userEvent.setup();
    const button = screen.getByRole('button', { name: 'Use demo token' });
    expect(button).toBeDisabled();
    const input = screen.getByLabelText('Demo bearer token');
    expect(input).toHaveAttribute('type', 'password');
    await user.type(input, '  synthetic-test-credential  ');
    await user.click(button);
    expect(connect).toHaveBeenCalledWith('synthetic-test-credential');
    expect(input).toHaveValue('');
  });

  it('authenticates JSON, reads and multipart uploads without putting credentials in URLs', async () => {
    const fetcher = vi.fn().mockImplementation(async () => new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetcher);
    const client = new ApiClient(new HttpTransport('', 1000, () => ({ Authorization: 'Bearer synthetic-test-credential' })));
    await client.getSession('demo-session');
    await client.command('demo-session', 'stop', { expected_revision: 1, reason_code: 'USER_STOP' }, 'same-intent');
    fetcher.mockImplementationOnce(async () => new Response('{"image_id":"frame"}', { status: 201 }));
    await client.uploadImage('demo-session', new Blob(['synthetic'], { type: 'image/png' }), 'identity', 1, 'frame-key');
    for (const [url, options] of fetcher.mock.calls) {
      expect(url).not.toContain('credential');
      expect(options.headers.Authorization).toBe('Bearer synthetic-test-credential');
    }
    expect(fetcher.mock.calls[1][1].headers['Idempotency-Key']).toBe('same-intent');
    expect(fetcher.mock.calls[2][1].headers['Content-Type']).toBeUndefined();
  });

  it('surfaces rejected authentication as an API error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 401 })));
    const client = new ApiClient(new HttpTransport());
    await expect(client.getSession('demo-session')).rejects.toMatchObject({ status: 401 });
  });
});
