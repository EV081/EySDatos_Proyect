import pytest

from client.fakes import FakeChannel, FakeDirectory, FakeDiscord
from client.orchestrator import Orchestrator
from client.privacy import NOTICE_VERSION
from crypto import KdfParams

ALICE, BOB, CAROL = "111111111111111111", "222222222222222222", "333333333333333333"
PASSWORD = "contraseña-maestra-123"
FAST_KDF = KdfParams(1, 64, 1)


class Clock:
    def __init__(self, now: float = 1_800_000_000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class World:
    """Dos usuarios (Alice y Bob) sobre un directorio y un canal falsos y compartidos."""

    def __init__(self, tmp_path, clock):
        self.clock, self.tmp = clock, tmp_path
        self.directory, self.channel = FakeDirectory(), FakeChannel()
        self.discord = {}
        self.orch = {}

    def user(self, discord_id, create=True) -> Orchestrator:
        discord = FakeDiscord(self.channel)
        orch = Orchestrator(self.tmp / discord_id, self.directory, discord, self.clock, FAST_KDF)
        self.discord[discord_id], self.orch[discord_id] = discord, orch
        if create:
            orch.create_identity(discord_id, PASSWORD, NOTICE_VERSION)
        return orch

    def restart(self, discord_id) -> Orchestrator:
        """Cierra y reabre la app de un usuario: se pierde la memoria, no el disco."""
        self.orch[discord_id].lock()
        self.discord[discord_id].receiver = None
        orch = self.user(discord_id, create=False)
        orch.unlock(PASSWORD)
        return orch

    def flush(self):
        while self.channel.flush():
            pass

    def plaintexts(self, orch, peer):
        return [(e["dir"], e["text"], e["status"]) for e in orch.history(peer)]


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def world(tmp_path, clock):
    return World(tmp_path, clock)


@pytest.fixture
def pair(world):
    """Alice y Bob con identidad creada y agregados como contactos."""
    alice, bob = world.user(ALICE), world.user(BOB)
    alice.add_contact(BOB, "Bob")
    bob.add_contact(ALICE, "Alice")
    return world, alice, bob
