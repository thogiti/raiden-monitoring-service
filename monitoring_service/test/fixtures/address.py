import pytest
import random
from monitoring_service.utils import privkey_to_addr
from monitoring_service.messages import BalanceProof
from sha3 import keccak_256


@pytest.fixture
def get_random_privkey():
    return lambda: "0x%064x" % random.randint(
        1,
        0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    )


@pytest.fixture
def get_random_address(get_random_privkey):
    def f():
        return privkey_to_addr(get_random_privkey())
    return f


@pytest.fixture
def get_random_bp(get_random_address):
    """Returns a balance proof filled in with a random values"""
    def f(participant1: str = None, participant2: str = None, channel_address: str = None):
        p1 = participant1 or get_random_address()
        p2 = participant2 or get_random_address()
        channel_address = channel_address or get_random_address()
        msg = BalanceProof(channel_address, p1, p2)
        msg.nonce = random.randint(0, 0xffffffffffffffff)
        msg.transferred_amount = random.randint(0, 0xffffffffffffffff)  # actual maximum is uint256
        # locksroot and extra_hash are 32bytes each
        hash_data = '%d' % random.randint(0, 0xffffffffffffffff)
        msg.locksroot = keccak_256(hash_data.encode()).hexdigest()
        hash_data = '%d' % random.randint(0, 0xffffffffffffffff)
        msg.extra_hash = keccak_256(hash_data.encode()).hexdigest()
        return msg
    return f


@pytest.fixture(scope='session')
def faucet_private_key():
    return '0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'


@pytest.fixture(scope='session')
def faucet_address(faucet_private_key):
    return privkey_to_addr(faucet_private_key)
