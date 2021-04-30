import pytest
from brownie import Wei, config


# change these fixtures for generic tests
@pytest.fixture
def currency(dai, usdc, weth):
    yield dai


@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


@pytest.fixture
def whale(accounts, web3, weth, dai, gov, chain):
    # big binance7 wallet
    acc = accounts.at("0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8", force=True)
    # big binance8 wallet
    # acc = accounts.at('0xf977814e90da44bfa03b6295a0616a897441acec', force=True)

    # lots of weth account
    wethAcc = accounts.at("0x767Ecb395def19Ab8d1b2FCc89B3DDfBeD28fD6b", force=True)

    weth.transfer(acc, weth.balanceOf(wethAcc), {"from": wethAcc})

    weth.transfer(gov, Wei("100 ether"), {"from": acc})
    dai.transfer(gov, Wei("10000 ether"), {"from": acc})

    assert weth.balanceOf(acc) > 0
    yield acc


@pytest.fixture()
def strategist(accounts, whale, currency):
    decimals = currency.decimals()
    currency.transfer(accounts[1], 100 * (10 ** decimals), {"from": whale})
    yield accounts[1]


@pytest.fixture
def samdev(accounts):
    yield accounts.at("0xC3D6880fD95E06C816cB030fAc45b3ffe3651Cb0", force=True)


@pytest.fixture
def gov(accounts):
    yield accounts[3]


@pytest.fixture
def rewards(gov):
    yield gov  # TODO: Add rewards contract


@pytest.fixture
def guardian(accounts):
    # YFI Whale, probably
    yield accounts[2]


@pytest.fixture
def keeper(accounts):
    # This is our trusty bot!
    yield accounts[4]


@pytest.fixture
def rando(accounts):
    yield accounts[9]


# specific addresses
@pytest.fixture
def usdc(interface):
    yield interface.ERC20("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")


@pytest.fixture
def dai(interface):
    yield interface.ERC20("0x6b175474e89094c44da98b954eedeac495271d0f")


@pytest.fixture
def weth(interface):
    yield interface.IWETH("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")


@pytest.fixture
def cdai(interface):
    yield interface.CErc20I("0x5d3a536e4d6dbd6114cc1ead35777bab948e3643")


@pytest.fixture
def cUsdc(interface):
    yield interface.CErc20I("0x39AA39c021dfbaE8faC545936693aC917d5E7563")


@pytest.fixture
def crUsdc(interface):
    yield interface.CErc20I("0x44fbeBd2F576670a6C33f6Fc0B00aA8c5753b322")


@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


# @pytest.fixture(scope="module", autouse=True)
# def shared_setup(module_isolation):
#    pass


@pytest.fixture
def vault(gov, rewards, guardian, currency, pm):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault, currency, gov, rewards, "", "")
    yield vault


@pytest.fixture
def Vault(pm):
    yield pm(config["dependencies"][0]).Vault


@pytest.fixture
def strategy(strategist, keeper, vault, Strategy, cdai):
    strategy = strategist.deploy(Strategy, vault, cdai)
    strategy.setKeeper(keeper)

    yield strategy


@pytest.fixture
def strategy_deployed(strategy):
    yield strategy
