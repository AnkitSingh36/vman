import { useCallback, useEffect, useRef, useState } from 'react';
import { IMAGE_MAX_BYTES, IMAGE_TYPES } from '../api/types';

/** Provisional client-side downscale; A-01 freezes the real pixel limits (D08). */
export const MAX_DIMENSION = 2048;

type CamState = 'IDLE' | 'STARTING' | 'LIVE' | 'CAPTURED' | 'DENIED' | 'UNSUPPORTED' | 'ERROR';

export interface CapturedFrame {
  blob: Blob;
  url: string;
  width: number;
  height: number;
}

/** Re-encode via canvas: strips EXIF/location metadata and bounds dimensions. Server still verifies. */
export async function reencode(source: CanvasImageSource, w: number, h: number): Promise<CapturedFrame | null> {
  const scale = Math.min(1, MAX_DIMENSION / Math.max(w, h));
  const cw = Math.max(1, Math.round(w * scale));
  const ch = Math.max(1, Math.round(h * scale));
  const canvas = document.createElement('canvas');
  canvas.width = cw;
  canvas.height = ch;
  const ctx = canvas.getContext?.('2d');
  if (!ctx || !canvas.toBlob) return null;
  ctx.drawImage(source, 0, 0, cw, ch);
  const blob = await new Promise<Blob | null>((r) => canvas.toBlob(r, 'image/jpeg', 0.88));
  if (!blob) return null;
  return { blob, url: URL.createObjectURL(blob), width: cw, height: ch };
}

export function validateFile(f: File): string | null {
  if (!(IMAGE_TYPES as readonly string[]).includes(f.type)) return 'Only JPEG or PNG images can be used.';
  if (f.size > IMAGE_MAX_BYTES) return 'That image is larger than 10 MiB.';
  return null;
}

async function fileToFrame(f: File): Promise<CapturedFrame | null> {
  try {
    const bmp = await createImageBitmap(f);
    const out = await reencode(bmp, bmp.width, bmp.height);
    bmp.close?.();
    if (out) return out;
  } catch {
    /* fall through */
  }
  // Fallback (e.g. no canvas): keep the original bytes; server strips metadata.
  return { blob: f, url: URL.createObjectURL(f), width: 0, height: 0 };
}

interface Props {
  /** Short description of what to frame (from the approved interaction, or the identity step). */
  instruction?: string;
  /** Called with the user-selected frame; parent shows explicit Send. */
  onFrame: (frame: CapturedFrame | null) => void;
  disabled?: boolean;
  /** When true, camera stream is stopped immediately (stop/offline/background). */
  suspend?: boolean;
}

export function CameraCapture({ instruction, onFrame, disabled, suspend }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [state, setState] = useState<CamState>('IDLE');
  const [frame, setFrame] = useState<CapturedFrame | null>(null);
  const [error, setError] = useState<string | null>(null);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => () => stopStream(), [stopStream]);
  useEffect(() => {
    if (suspend) {
      stopStream();
      setState((s) => (s === 'LIVE' || s === 'STARTING' ? 'IDLE' : s));
    }
  }, [suspend, stopStream]);
  useEffect(() => () => {
    if (frame) URL.revokeObjectURL(frame.url);
  }, [frame]);

  const select = (f: CapturedFrame | null) => {
    setFrame(f);
    onFrame(f);
  };

  const startCamera = async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setState('UNSUPPORTED');
      return;
    }
    setState('STARTING');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
      streamRef.current = stream;
      setState('LIVE');
      requestAnimationFrame(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          void videoRef.current.play().catch(() => undefined);
        }
      });
    } catch (e) {
      const name = (e as { name?: string })?.name;
      setState(name === 'NotAllowedError' || name === 'SecurityError' ? 'DENIED' : 'ERROR');
    }
  };

  const snap = async () => {
    const v = videoRef.current;
    if (!v || !v.videoWidth) return;
    const out = await reencode(v, v.videoWidth, v.videoHeight);
    if (!out) {
      setError('Could not capture this frame.');
      return;
    }
    stopStream();
    setState('CAPTURED');
    select(out);
  };

  const retake = () => {
    select(null);
    void startCamera();
  };

  const onPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = '';
    if (!f) return;
    const bad = validateFile(f);
    if (bad) {
      setError(bad);
      return;
    }
    const out = await fileToFrame(f);
    stopStream();
    setState('CAPTURED');
    select(out);
  };

  return (
    <div className="camera" aria-label="Camera">
      {instruction ? <p className="camera-instruction">{instruction}</p> : null}
      {state === 'LIVE' || state === 'STARTING' ? (
        <div className="preview">
          <video ref={videoRef} playsInline muted aria-label="Live camera preview (stays on this device)" />
          <div className="row">
            <button type="button" onClick={snap} disabled={disabled || state !== 'LIVE'}>
              Take snapshot
            </button>
            <button type="button" onClick={() => { stopStream(); setState('IDLE'); }}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}
      {state === 'CAPTURED' && frame ? (
        <div className="preview">
          <img src={frame.url} alt="Selected snapshot (not sent yet)" />
          <p className="small muted">Selected snapshot — not sent until you press Send.</p>
          <div className="row">
            <button type="button" onClick={retake} disabled={disabled}>
              Retake
            </button>
            <button type="button" onClick={() => { select(null); setState('IDLE'); }} disabled={disabled}>
              Discard
            </button>
          </div>
        </div>
      ) : null}
      {state !== 'LIVE' && state !== 'STARTING' && state !== 'CAPTURED' ? (
        <div className="row">
          <button type="button" onClick={startCamera} disabled={disabled}>
            Open camera
          </button>
          <label className="file-pick">
            Choose photo
            <input type="file" accept="image/jpeg,image/png" capture="environment" onChange={onPick} disabled={disabled} />
          </label>
        </div>
      ) : null}
      {state === 'DENIED' ? <p role="alert">Camera permission was denied. You can choose a photo instead, or use another option below.</p> : null}
      {state === 'UNSUPPORTED' ? <p role="alert">Live camera is not available in this browser. Choose a photo instead.</p> : null}
      {state === 'ERROR' ? <p role="alert">The camera could not be started. Choose a photo instead.</p> : null}
      {error ? <p role="alert">{error}</p> : null}
    </div>
  );
}
