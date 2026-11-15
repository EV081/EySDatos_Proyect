-- Los desbloqueos habituales tienen nonces separados del registro y la cancelación.
ALTER TABLE challenges DROP CONSTRAINT IF EXISTS challenges_purpose_check;
ALTER TABLE challenges ADD CONSTRAINT challenges_purpose_check
    CHECK (purpose IN ('register', 'cancel', 'unlock'));
