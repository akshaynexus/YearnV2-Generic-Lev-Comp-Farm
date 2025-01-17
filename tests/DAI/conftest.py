import pytest
from brownie import Wei, config


# change these fixtures for generic tests
@pytest.fixture
def currency(dai):
    # this one is dai:
    yield dai
    # this one is weth:
    # yield interface.ERC20('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2')


@pytest.fixture
def vault(gov, rewards, guardian, currency, pm, Vault):

    vault = gov.deploy(Vault)
    vault.initialize(currency, gov, rewards, "", "", guardian)
    vault.setDepositLimit(2 ** 256 - 1, {"from": gov})

    yield vault


@pytest.fixture
def rewards(gov):
    yield gov  # TODO: Add rewards contract


@pytest.fixture
def Vault(pm):
    yield pm(config["dependencies"][0]).Vault


@pytest.fixture
def weth(interface):

    yield interface.ERC20("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c")


@pytest.fixture
def strategy_changeable(YearnWethCreamStratV2, YearnDaiCompStratV2):
    # yield YearnWethCreamStratV2
    yield YearnDaiCompStratV2


@pytest.fixture
def whale(accounts, web3, weth, dai, usdc, gov, chain):
    # big binance7 wallet
    # acc = accounts.at('0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8', force=True)
    # big binance8 wallet
    acc2 = accounts.at("0xF977814e90dA44bFA03b6295A0616a897441aceC", force=True)

    acc = accounts.at("0x631Fc1EA2270e98fbD9D92658eCe0F5a269Aa161", force=True)
    usdc.transfer(acc, usdc.balanceOf(acc2), {"from": acc2})
    # lots of weth account
    # if weth transfer fails change to new weth account
    # wethAcc = accounts.at('0x1840c62fD7e2396e470377e6B2a833F3A1E96221', force=True)

    # weth.transfer(acc, weth.balanceOf(wethAcc),{"from": wethAcc} )

    # wethDeposit = 100 *1e18
    daiDeposit = 10000 * 1e18

    # assert weth.balanceOf(acc)  > wethDeposit
    assert dai.balanceOf(acc) > daiDeposit

    # weth.transfer(gov, wethDeposit,{"from": acc} )
    dai.transfer(gov, daiDeposit, {"from": acc})

    #  assert  weth.balanceOf(acc) > 0
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


@pytest.fixture
def dai(interface):
    yield interface.ERC20("0x1AF3F329e8BE154074D8769D1FFa4eE058B1DBc3")


@pytest.fixture
def usdc(interface):
    yield interface.ERC20("0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d")


# any strategy just deploys base strategy can be used because they have the same interface
@pytest.fixture
def strategy_generic(YearnDaiCompStratV2):
    # print('Do you want to use deployed strategy? (y)')
    # if input() == 'y' or 'Y':
    print("Enter strategy address")
    yield YearnDaiCompStratV2.at(input())


@pytest.fixture
def vault_generic(Vault):
    print("Enter vault address")
    yield Vault.at(input())


@pytest.fixture
def strategist_generic(accounts):
    print("Enter strategist address")
    yield accounts.at(input(), force=True)


@pytest.fixture
def governance_generic(accounts):
    print("Enter governance address")
    yield accounts.at(input(), force=True)


@pytest.fixture
def whale_generic(accounts):
    print("Enter whale address")
    yield accounts.at(input(), force=True)


@pytest.fixture
def want_generic(interface):
    print("Enter want address")
    yieldinterface.ERC20(input())


@pytest.fixture
def live_vault(Vault):
    yield Vault.at("0x9B142C2CDAb89941E9dcd0B6C1cf6dEa378A8D7C")


@pytest.fixture
def live_strategy(Strategy):
    yield YearnDaiCompStratV2.at("0x4C6e9d7E5d69429100Fcc8afB25Ea980065e2773")


@pytest.fixture
def live_strategy_dai_030(Strategy):
    yield Strategy.at("0x4031afd3B0F71Bace9181E554A9E680Ee4AbE7dF")


@pytest.fixture
def live_vault_usdc_030(Vault):
    yield Vault.at("0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9")


@pytest.fixture
def live_strategy_usdc_030(Strategy):
    yield Strategy.at("0x4D7d4485fD600c61d840ccbeC328BfD76A050F87")


@pytest.fixture
def live_vault_dai_030(Vault):
    yield Vault.at("0x19D3364A399d251E894aC732651be8B0E4e85001")


@pytest.fixture
def live_strategy_dai2(Strategy):
    yield Strategy.at("0x2D1b8C783646e146312D317E550EF80EC1Cb08C3")


@pytest.fixture
def live_strategy_usdc3(Strategy):
    yield Strategy.at("0x31576ac682ee0A15c48C4baC24c567f27CA1b7cD")


@pytest.fixture
def live_strategy_usdc4(Strategy):
    yield Strategy.at("0xC10363fa66d9c12724e56f269D0438B26581b2eA")


@pytest.fixture
def live_vault_usdc3(Vault):
    yield Vault.at("0xe2F6b9773BF3A015E2aA70741Bde1498bdB9425b")


@pytest.fixture
def live_strategy_dai3(Strategy):
    yield Strategy.at("0x5A9D49679319FCF3AcFe5559602Dbf31A221BaD6")


@pytest.fixture
def live_strategy_dai4(Strategy):
    yield Strategy.at("0x001F751cdfee02e2F0714831bE2f8384db0F71a2")


@pytest.fixture
def live_vault_dai3(Vault):
    yield Vault.at("0xBFa4D8AA6d8a379aBFe7793399D3DdaCC5bBECBB")


@pytest.fixture
def live_vault_dai2(Vault):
    yield Vault.at("0x1b048bA60b02f36a7b48754f4edf7E1d9729eBc9")


@pytest.fixture
def live_vault_weth(Vault):
    yield Vault.at("0xf20731f26e98516dd83bb645dd757d33826a37b5")


@pytest.fixture
def live_strategy_weth(YearnWethCreamStratV2):
    yield YearnDaiCompStratV2.at("0x97785a81b3505ea9026b2affa709dfd0c9ef24f6")


@pytest.fixture
def dai(interface):
    yield interface.ERC20("0x1AF3F329e8BE154074D8769D1FFa4eE058B1DBc3")


# uniwethwbtc
@pytest.fixture
def uni_wethwbtc(interface):
    yield interface.ERC20("0xBb2b8038a1640196FbE3e38816F3e67Cba72D940")


@pytest.fixture
def samdev(accounts):
    yield accounts.at("0xC3D6880fD95E06C816cB030fAc45b3ffe3651Cb0", force=True)


@pytest.fixture
def earlyadopter(accounts):
    yield accounts.at("0x769B66253237107650C3C6c84747DFa2B071780e", force=True)


@pytest.fixture
def comp(interface):
    yield interface.ERC20("0x4437743ac02957068995c48E08465E0EE1769fBE")


@pytest.fixture
def cdai(interface):
    yield interface.CErc20I("0x5F30fDDdCf14a0997a52fdb7D7F23b93F0f21998")

@pytest.fixture
def crdai(interface):
    yield interface.CErc20I("0x9095e8d707E40982aFFce41C61c10895157A1B22")

# @pytest.fixture(autouse=True)
# def isolation(fn_isolation):
#    pass
@pytest.fixture(scope="module", autouse=True)
def shared_setup(module_isolation):
    pass


@pytest.fixture
def gov(accounts):
    yield accounts[0]


@pytest.fixture
def live_gov(accounts):
    yield accounts.at("0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52", force=True)


# uniswap weth/wbtc
@pytest.fixture()
def whaleU(accounts, history, web3, shared_setup):
    acc = accounts.at("0xf2d373481e1da4a8ca4734b28f5a642d55fda7d3", force=True)
    yield acc


@pytest.fixture
def rando(accounts):
    yield accounts[9]


@pytest.fixture()
def seededvault(vault, dai, rando):
    # Make it so vault has some AUM to start
    amount = Wei("10000 ether")
    token.approve(vault, amount, {"from": rando})
    vault.deposit(amount, {"from": rando})
    assert token.balanceOf(vault) == amount
    assert vault.totalDebt() == 0  # No connected strategies yet
    yield vault


@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


@pytest.fixture()
def strategy(strategist, gov, keeper, vault, Strategy, cdai, crdai):
    strategy = strategist.deploy(Strategy, vault, cdai, crdai)
    strategy.setKeeper(keeper)

    rate_limit = 1_000_000 * 1e18

    debt_ratio = 9_500  # 100%
    vault.addStrategy(strategy, debt_ratio, 0, rate_limit, 1000, {"from": gov})

    yield strategy


@pytest.fixture()
def largerunningstrategy(gov, strategy, dai, vault, whale):

    amount = Wei("499000 ether")
    dai.approve(vault, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})

    strategy.harvest({"from": gov})

    # do it again with a smaller amount to replicate being this full for a while
    amount = Wei("1000 ether")
    dai.approve(vault, amount, {"from": whale})
    vault.deposit(amount, {"from": whale})
    strategy.harvest({"from": gov})

    yield strategy


@pytest.fixture()
def enormousrunningstrategy(gov, largerunningstrategy, dai, vault, whale):
    dai.approve(vault, dai.balanceOf(whale), {"from": whale})
    vault.deposit(dai.balanceOf(whale), {"from": whale})

    collat = 0

    while collat < largerunningstrategy.collateralTarget() / 1.001e18:

        largerunningstrategy.harvest({"from": gov})
        deposits, borrows = largerunningstrategy.getCurrentPosition()
        collat = borrows / deposits
        print(collat)

    yield largerunningstrategy
