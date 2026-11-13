'use client';
import { useEffect, useMemo, useRef } from 'react';
import qrcode from 'qrcode-generator';

const QUIET = 4; // margen en blanco que exige el estándar para que el lector encuentre el código

/** Dibuja el QR como SVG en línea (no usa <img>, así que la CSP no cambia). Siempre negro sobre blanco. */
export function QrCode({ text, label }: { text: string; label: string }) {
  const { size, path } = useMemo(() => {
    const qr = qrcode(0, 'M');
    qr.addData(text, 'Alphanumeric');
    qr.make();
    const n = qr.getModuleCount();
    let d = '';
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.isDark(r, c)) d += `M${c + QUIET} ${r + QUIET}h1v1h-1z`;
    return { size: n + QUIET * 2, path: d };
  }, [text]);
  return (
    <svg className="qr" viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label} shapeRendering="crispEdges">
      <rect width={size} height={size} fill="#fff" />
      <path d={path} fill="#000" />
    </svg>
  );
}

function cameraError(err: unknown): string {
  const name = (err as { name?: string } | null)?.name;
  if (name === 'NotAllowedError' || name === 'SecurityError') return 'No diste permiso para usar la cámara.';
  if (name === 'NotFoundError' || name === 'OverconstrainedError') return 'No se encontró ninguna cámara en este equipo.';
  if (name === 'NotReadableError') return 'La cámara está en uso por otra aplicación.';
  return 'No se pudo abrir la cámara.';
}

interface ScannerProps {
  /** Recibe el texto de cada QR leído. Devuelve true si lo aceptó (se deja de escanear). */
  onText: (text: string) => boolean;
  onError: (message: string) => void;
}

/** Lee códigos QR con la cámara. La imagen se procesa en el navegador y no se guarda ni se envía. */
export function QrScanner({ onText, onError }: ScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const handlers = useRef({ onText, onError });
  handlers.current = { onText, onError };

  useEffect(() => {
    let stopped = false;
    let raf = 0;
    let stream: MediaStream | null = null;
    const stop = () => stream?.getTracks().forEach((t) => t.stop());

    (async () => {
      try {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error('sin cámara');
        const { default: jsQR } = await import('jsqr');
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
        const video = videoRef.current;
        if (stopped || !video) return stop();
        video.srcObject = stream;
        await video.play();
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        const scan = () => {
          if (stopped) return;
          if (ctx && video.readyState >= 2 && video.videoWidth > 0) {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            ctx.drawImage(video, 0, 0);
            const frame = ctx.getImageData(0, 0, canvas.width, canvas.height);
            const hit = jsQR(frame.data, frame.width, frame.height, { inversionAttempts: 'dontInvert' });
            if (hit?.data && handlers.current.onText(hit.data)) return;
          }
          raf = requestAnimationFrame(scan);
        };
        scan();
      } catch (err) {
        if (!stopped) handlers.current.onError(cameraError(err));
      }
    })();

    return () => {
      stopped = true;
      cancelAnimationFrame(raf);
      stop();
    };
  }, []);

  return <video ref={videoRef} className="qr-video" muted playsInline aria-label="Vista de la cámara" />;
}
