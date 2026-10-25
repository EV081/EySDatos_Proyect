import pytest

from crypto import Identity, Initiator, Responder
from crypto.identity import KdfParams

FAST_KDF = KdfParams(time_cost=1, memory_kib=64, parallelism=1)  # solo para que los tests sean rápidos

ALICE, BOB = "111111111111111111", "222222222222222222"


class Clock:
    def __init__(self, now: float = 1_800_000_000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def alice():
    return Identity.create()


@pytest.fixture
def bob():
    return Identity.create()


@pytest.fixture
def handshake(alice, bob, clock):
    """Ejecuta un handshake completo y devuelve todas las piezas."""
    init = Initiator(alice, ALICE, BOB, bob.public_key, clock)
    resp = Responder(bob, BOB, ALICE, alice.public_key, clock=clock)
    hs1 = init.start()
    hs2 = resp.respond(hs1)
    hs3, sess_a = init.finish(hs2)
    sess_b = resp.finish(hs3)
    return {"init": init, "resp": resp, "hs1": hs1, "hs2": hs2, "hs3": hs3, "a": sess_a, "b": sess_b}
