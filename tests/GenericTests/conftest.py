import pytest
from brownie import Wei, config


from tests.commonconf import daiAddr, wethAddr, usdcAddr, cdaiAddr, cUSDCAddr, crUSDCAddr, crDaiAddr, daiAccAddr, WethAccAddr


# change these fixtures for generic tests
@pytest.fixture
def currency(dai):
    yield dai


@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


@pytest.fixture
def whale(accounts, web3, weth, dai, gov, chain):
    # big binance7 wallet
    daiAcc = accounts.at(daiAccAddr, force=True)
    # big binance8 wallet
    # daiAcc = accounts.at('0xf977814e90da44bfa03b6295a0616a897441acec', force=True)

    # lots of weth account
    wethAcc = accounts.at(WethAccAddr, force=True)

    weth.transfer(daiAcc, weth.balanceOf(wethAcc), {"from": wethAcc})

    weth.transfer(gov, Wei("100 ether"), {"from": daiAcc})
    dai.transfer(gov, Wei("10000 ether"), {"from": daiAcc})

    assert weth.balanceOf(daiAcc) > 0
    yield daiAcc


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
    yield interface.ERC20(usdcAddr)


@pytest.fixture
def dai(interface):
    yield interface.ERC20(daiAddr)


@pytest.fixture
def weth(interface):
    yield interface.IWETH(wethAddr)


@pytest.fixture
def cdai(interface):
    yield interface.CErc20I(cdaiAddr)


@pytest.fixture
def cUsdc(interface):
    yield interface.CErc20I(cUSDCAddr)


@pytest.fixture
def crUsdc(interface):
    yield interface.CErc20I(crUSDCAddr)

@pytest.fixture
def crdai(interface):
    yield interface.CErc20I(crDaiAddr)

@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


# @pytest.fixture(scope="module", autouse=True)
# def shared_setup(module_isolation):
#    pass


@pytest.fixture
def vault(Vault, gov, rewards, guardian, currency, pm):
    vault = gov.deploy(Vault)
    vault.initialize(
        currency,
        gov,
        rewards,
        "",
        "",
        guardian
    )
    vault.setDepositLimit(2 ** 256 - 1, {"from": gov})

    yield vault


@pytest.fixture
def Vault(pm):
    yield pm(config["dependencies"][0]).Vault


@pytest.fixture
def strategy(strategist, keeper, vault, Strategy, cdai, crdai):
    strategy = strategist.deploy(Strategy, vault, cdai, crdai)
    strategy.setKeeper(keeper)

    yield strategy


@pytest.fixture
def strategy_deployed(strategy):
    yield strategy
