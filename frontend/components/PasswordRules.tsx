import { PASSWORD_RULES } from '@/lib/password';

/** Lista de requisitos que se marca a medida que se escribe la contraseña. */
export function PasswordRules({ password }: { password: string }) {
  return (
    <ul className="pw-rules" aria-label="Requisitos de la contraseña">
      {PASSWORD_RULES.map((rule) => {
        const ok = rule.test(password);
        return (
          <li key={rule.id} className={ok ? 'ok' : undefined}>
            <span aria-hidden="true">{ok ? '✓' : '•'}</span> {rule.label}
            <span className="sr-only">{ok ? ' (cumplido)' : ' (pendiente)'}</span>
          </li>
        );
      })}
    </ul>
  );
}
