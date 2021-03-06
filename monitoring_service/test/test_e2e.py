import gevent
import pytest
from raiden_libs.blockchain import BlockchainListener
from raiden_contracts.contract_manager import CONTRACT_MANAGER
import logging


class Validator(BlockchainListener):
    def __init__(self, web3):
        super().__init__(
            web3,
            CONTRACT_MANAGER,
            'MonitoringService',
            poll_interval=1
        )
        self.events = list()
        self.add_unconfirmed_listener(
            'NewBalanceProofReceived', lambda event: self.append_message(event)
        )

    def append_message(self, event):
        self.events.append(event)


@pytest.fixture
def blockchain_validator(web3):
    validator = Validator(web3)
    validator.start()
    yield validator
    validator.stop()


def test_e2e(
    web3,
    monitoring_service,
    generate_raiden_clients,
    monitoring_service_contract,
    wait_for_blocks,
    blockchain_validator,
    custom_token,
    raiden_service_bundle
):
    """Test complete message lifecycle
        1) client opens channel & submits monitoring request
        2) other client closes channel
        3) MS registers channelClose event
        4) MS calls monitoring contract update
        5) wait for channel settle
        6) MS claims the reward
    """
    monitoring_service.start()

    reward_amount = 1
    initial_balance = monitoring_service_contract.functions.balances(
        monitoring_service.address
    ).call()
    c1, c2 = generate_raiden_clients(2)
    node_deposit = 10
    custom_token.functions.approve(
        raiden_service_bundle.address,
        node_deposit
    ).transact(
        {'from': c1.address}
    )
    raiden_service_bundle.functions.deposit(node_deposit).transact(
        {'from': c1.address}
    )
    channel_id = c1.open_channel(c2.address)
    balance_proof_c1 = c1.get_balance_proof(
        c2.address,
        nonce=1,
        transferred_amount=5,
        locked_amount=0,
        locksroot='0x%064x' % 0,
        additional_hash='0x%064x' % 0
    )
    balance_proof_c2 = c2.get_balance_proof(
        c1.address,
        nonce=2,
        transferred_amount=6,
        locked_amount=0,
        locksroot='0x%064x' % 0,
        additional_hash='0x%064x' % 0
    )
    logging.getLogger('raiden_libs.blockchain').setLevel(logging.DEBUG)

    monitor_request = c1.get_monitor_request(
        c2.address,
        balance_proof_c2,
        reward_amount,
        monitoring_service.address
    )

    monitoring_service.transport.receive_fake_data(monitor_request.serialize_full())
    gevent.sleep(0)
    assert channel_id in monitoring_service.monitor_requests

    c2.close_channel(c1.address, balance_proof_c1)
    # wait till monitor's blockchain confirms closeChannel event...
    wait_for_blocks(10)
    gevent.sleep(1)
    # wait till validator confirms NewBalanceProofReceived event...
    wait_for_blocks(10)
    gevent.sleep(1)
    assert len(blockchain_validator.events) == 1

    c2.settle_channel(
        c1.address,
        (balance_proof_c2.transferred_amount, balance_proof_c1.transferred_amount),
        (balance_proof_c2.locked_amount, balance_proof_c1.locked_amount),
        (balance_proof_c1.locksroot, balance_proof_c1.locksroot)
    )
    wait_for_blocks(10)
    gevent.sleep(1)
    # channel is settled
    wait_for_blocks(1)
    gevent.sleep(1)
    final_balance = monitoring_service_contract.functions.balances(
        monitoring_service.address
    ).call()
    assert final_balance == (initial_balance + reward_amount)
