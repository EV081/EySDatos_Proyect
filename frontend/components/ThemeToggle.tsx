'use client';
import { useEffect, useState } from 'react';

const KEY = 'e2ee.theme';
type Theme = 'light' | 'dark';

function systemTheme(): Theme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

// Alterna claro/oscuro. La elección se recuerda solo en este navegador (localStorage); sin elección sigue al sistema.
export function ThemeToggle({ className = '' }: { className?: string }) {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    const current = document.documentElement.dataset.theme;
    setTheme(current === 'light' || current === 'dark' ? current : systemTheme());
  }, []);

  const toggle = () => {
    const next: Theme = (theme ?? systemTheme()) === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* sin almacenamiento: el cambio vale solo para esta sesión */
    }
    setTheme(next);
  };

  const dark = theme === 'dark';
  return (
    <button
      type="button"
      className={`theme-toggle ${className}`}
      onClick={toggle}
      aria-label={dark ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}
      title={dark ? 'Tema claro' : 'Tema oscuro'}
    >
      {theme === null ? '' : dark ? '☀️' : '🌙'}
    </button>
  );
}
