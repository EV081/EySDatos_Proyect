// Reglas de las contraseñas nuevas (contraseña maestra y la del archivo exportado).
// Las letras se evalúan con Unicode: "Ñ" cuenta como mayúscula y "ñ" como minúscula.
export const MIN_PASSWORD_LENGTH = 10;

export interface PasswordRule {
  id: 'length' | 'upper' | 'lower' | 'special';
  label: string;
  test: (password: string) => boolean;
}

export const PASSWORD_RULES: readonly PasswordRule[] = [
  { id: 'length', label: `Al menos ${MIN_PASSWORD_LENGTH} caracteres`, test: (p) => [...p].length >= MIN_PASSWORD_LENGTH },
  { id: 'upper', label: 'Una letra mayúscula', test: (p) => /\p{Lu}/u.test(p) },
  { id: 'lower', label: 'Una letra minúscula', test: (p) => /\p{Ll}/u.test(p) },
  // Especial: cualquier carácter que no sea letra, número ni espacio (!, @, #, -, _, ¿, etc.).
  { id: 'special', label: 'Un carácter especial (por ejemplo ! @ # $ % - _)', test: (p) => /[^\p{L}\p{N}\s]/u.test(p) },
];

/** Reglas que la contraseña todavía no cumple (vacío = válida). */
export function passwordProblems(password: string): PasswordRule[] {
  return PASSWORD_RULES.filter((rule) => !rule.test(password));
}

export const isStrongPassword = (password: string) => passwordProblems(password).length === 0;

export const WEAK_PASSWORD_MESSAGE =
  'La contraseña debe tener al menos 10 caracteres, una mayúscula, una minúscula y un carácter especial.';
