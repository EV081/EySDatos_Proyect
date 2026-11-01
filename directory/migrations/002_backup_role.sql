-- Rol de solo lectura para las copias de seguridad (F4): pg_dump no necesita escribir nada.
GRANT USAGE ON SCHEMA directory TO directory_backup;
GRANT SELECT ON keys, replaced_keys, oauth_states, auth_tokens, challenges TO directory_backup;
