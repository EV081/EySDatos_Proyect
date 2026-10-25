export function Banner({ text, info = false }: { text: string | null; info?: boolean }) {
  if (!text) return null;
  return (
    <div className={`banner${info ? ' info' : ''}`} role="alert">
      {text}
    </div>
  );
}
