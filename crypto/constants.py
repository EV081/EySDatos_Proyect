VERSION = 1
WIRE_PREFIX = "E2EE1:"
MAX_WIRE_LEN = 2000  # límite de un mensaje de Discord
MAX_PLAINTEXT = 900  # bytes por mensaje (cabe en 2000 caracteres con ids de 25 dígitos); el cliente parte los textos largos

HANDSHAKE_TTL = 300  # segundos que vive un intento de handshake
CLOCK_SKEW = 60  # tolerancia de reloj para un hs1 "del futuro"

ROTATE_AFTER_MESSAGES = 100
ROTATE_AFTER_SECONDS = 8 * 3600
HARD_LIMIT_FACTOR = 2  # pasado ROTATE * factor, la sesión deja de funcionar
REPLAY_WINDOW = 64

# Cada contexto separa el dominio de una firma: lo firmado con uno no sirve en otro.
CTX_PREFIX = b"e2ee-discord/v1 "
CTX_INITIATOR = b"handshake initiator"
CTX_RESPONDER = b"handshake responder"
CTX_REGISTER = b"directory register"
CTX_KEY_CHANGE = b"directory key change"

INFO_KEY_AB = b"e2ee-discord/v1 key A->B"
INFO_KEY_BA = b"e2ee-discord/v1 key B->A"
INFO_KEY_CONF = b"e2ee-discord/v1 key confirm"
LABEL_TAG_INITIATOR = b"A"
LABEL_TAG_RESPONDER = b"B"
AAD_MSG = b"e2ee-discord/v1 msg"
AAD_VAULT = b"e2ee-discord/v1 vault"
