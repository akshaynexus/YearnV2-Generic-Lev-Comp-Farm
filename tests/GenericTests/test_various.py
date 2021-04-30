from itertools import count
from brownie import Wei, reverts
from useful_methods import (
    genericStateOfStrat,
    stateOfStrat,
    genericStateOfVault,
    deposit,
    sleep,
)
import random
import brownie


def test_donations(strategy, web3, chain, vault, currency, whale, strategist, gov):
    deposit_limit = Wei("1_000_000 ether")

    vault.addStrategy(strategy, deposit_limit, deposit_limit, 50, {"from": gov})
    amount = Wei("500_000 ether")
    deposit(amount, whale, currency, vault)
    assert vault.strategies(strategy)[5] == 0
    strategy.harvest({"from": gov})
    assert vault.strategies(strategy)[6] == 0

    donation = Wei("1000 ether")

    # donation to strategy
    currency.transfer(strategy, donation, {"from": whale})
    assert vault.strategies(strategy)[6] == 0

    sleep(chain, 10)
    strategy.harvest({"from": gov})
    assert vault.strategies(strategy)[6] >= donation * 0.9999
    assert currency.balanceOf(vault) >= donation * 0.99999

    strategy.harvest({"from": gov})
    assert vault.strategies(strategy)[5] >= (donation + amount) * 0.99999

    # donation to vault
    currency.transfer(vault, donation, {"from": whale})
    assert (
        vault.strategies(strategy)[6] >= donation * 0.9999
        and vault.strategies(strategy)[6] < donation * 2
    )
    strategy.harvest({"from": gov})
    assert vault.strategies(strategy)[5] >= (donation * 2 + amount) * 0.9999
    strategy.harvest({"from": gov})

    assert (
        vault.strategies(strategy)[6] >= donation * 0.999
        and vault.strategies(strategy)[6] < donation * 2
    )
    # check share price is close to expected
    assert (
        vault.pricePerShare() > ((donation * 2 + amount) / amount) * 0.95 * 1e18
        and vault.pricePerShare() < ((donation * 2 + amount) / amount) * 1.05 * 1e18
    )


def test_good_migration(
    strategy, chain, Strategy, web3, vault, currency, whale, rando, gov, strategist
):
    # Call this once to seed the strategy with debt
    vault.addStrategy(strategy, 2 ** 256 - 1, 2 ** 256 - 1, 50, {"from": gov})

    amount1 = Wei("50_000 ether")
    deposit(amount1, whale, currency, vault)

    amount1 = Wei("500 ether")
    deposit(amount1, gov, currency, vault)

    strategy.harvest({"from": gov})
    sleep(chain, 10)
    strategy.harvest({"from": gov})

    strategy_debt = vault.strategies(strategy)[4]  # totalDebt
    prior_position = strategy.estimatedTotalAssets()
    assert strategy_debt > 0

    new_strategy = strategist.deploy(Strategy, vault, "", strategy.cToken())
    assert vault.strategies(new_strategy)[4] == 0
    assert currency.balanceOf(new_strategy) == 0

    # Only Governance can migrate
    with brownie.reverts():
        vault.migrateStrategy(strategy, new_strategy, {"from": rando})

    vault.migrateStrategy(strategy, new_strategy, {"from": gov})
    assert vault.strategies(strategy)[4] == 0
    assert vault.strategies(new_strategy)[4] == strategy_debt
    assert (
        new_strategy.estimatedTotalAssets() > prior_position * 0.999
        or new_strategy.estimatedTotalAssets() < prior_position * 1.001
    )


def test_vault_shares_generic(
    strategy, web3, chain, vault, currency, whale, strategist, gov, interface
):
    deposit_limit = Wei("1000 ether")
    # set limit to the vault
    vault.setDepositLimit(deposit_limit, {"from": gov})

    vault.addStrategy(strategy, deposit_limit, deposit_limit, 0, {"from": gov})

    assert vault.totalSupply() == 0
    amount1 = Wei("50 ether")
    deposit(amount1, whale, currency, vault)
    whale_share = vault.balanceOf(whale)
    deposit(amount1, gov, currency, vault)
    gov_share = vault.balanceOf(gov)

    assert gov_share == whale_share
    assert vault.pricePerShare() == 1e18
    assert vault.pricePerShare() * whale_share / 1e18 == amount1

    assert vault.pricePerShare() * whale_share / 1e18 == vault.totalAssets() / 2
    assert gov_share == whale_share

    strategy.harvest({"from": gov})
    # no profit yet
    whale_share = vault.balanceOf(whale)
    gov_share = vault.balanceOf(gov)
    assert gov_share > whale_share

    sleep(chain, 100)
    whale_share = vault.balanceOf(whale)
    gov_share = vault.balanceOf(gov)
    # no profit just aum fee. meaning total balance should be the same
    assert (gov_share + whale_share) * vault.pricePerShare() / 1e18 == 100 * 1e18

    strategy.harvest({"from": gov})
    whale_share = vault.balanceOf(whale)
    gov_share = vault.balanceOf(gov)
    # add strategy return
    assert vault.totalSupply() == whale_share + gov_share
    value = (gov_share + whale_share) * vault.pricePerShare() / 1e18
    assert (
        value * 0.99999 < vault.totalAssets() and value * 1.00001 > vault.totalAssets()
    )
    # check we are within 0.1% of expected returns
    # stateOfStrat(strategy, interface)
    assert (
        value < strategy.estimatedTotalAssets() * 1.001
        and value > strategy.estimatedTotalAssets() * 0.999
    )

    assert gov_share > whale_share


def test_vault_emergency_exit_generic(
    strategy, web3, chain, interface, vault, currency, whale, strategist, gov
):
    deposit_limit = Wei("1000000 ether")

    vault.addStrategy(strategy, deposit_limit, deposit_limit, 50, {"from": gov})

    amount0 = Wei("500 ether")
    deposit(amount0, whale, currency, vault)

    amount1 = Wei("50 ether")
    deposit(amount1, gov, currency, vault)

    strategy.harvest({"from": gov})
    sleep(chain, 30)

    assert vault.emergencyShutdown() == False

    vault.setEmergencyShutdown(True, {"from": gov})
    assert vault.emergencyShutdown()

    # genericStateOfStrat(strategy, currency, vault)
    # genericStateOfVault(vault, currency)
    ## emergency shutdown
    # stateOfStrat(strategy, interface)
    strategy.harvest({"from": gov})
    # stateOfStrat(strategy, interface)
    strategy.harvest({"from": gov})
    assert currency.balanceOf(vault) > amount0 + amount1
    assert strategy.estimatedTotalAssets() < Wei("0.01 ether")
    # Emergency shut down + harvest done
    # genericStateOfStrat(strategy, currency, vault)
    # genericStateOfVault(vault, currency)

    # Restore power
    vault.setEmergencyShutdown(False, {"from": gov})
    strategy.harvest({"from": gov})
    assert strategy.estimatedTotalAssets() > amount0 + amount1
    assert currency.balanceOf(vault) == 0

    # Withdraw All
    vault.withdraw(vault.balanceOf(gov), {"from": gov})


def test_strat_emergency_exit_generic(
    strategy, web3, chain, interface, vault, currency, whale, strategist, gov
):

    deposit_limit = Wei("1000000 ether")

    vault.addStrategy(strategy, deposit_limit, deposit_limit, 50, {"from": gov})

    amount0 = Wei("500 ether")
    deposit(amount0, whale, currency, vault)

    amount1 = Wei("50 ether")
    deposit(amount1, gov, currency, vault)

    strategy.harvest({"from": gov})
    sleep(chain, 31)

    assert strategy.emergencyExit() == False

    strategy.setEmergencyExit({"from": gov})
    assert strategy.emergencyExit()

    # genericStateOfStrat(strategy, currency, vault)
    # genericStateOfVault(vault, currency)
    ## emergency shutdown

    strategy.harvest({"from": gov})

    assert currency.balanceOf(vault) >= amount0 + amount1
    # Emergency shut down + harvest done
    # genericStateOfStrat(strategy, currency, vault)
    # genericStateOfVault(vault, currency)

    # Withdraw All
    vault.withdraw(vault.balanceOf(gov), {"from": gov})


def test_strat_graceful_exit_generic(
    strategy, web3, chain, vault, currency, whale, strategist, gov
):

    deposit_limit = Wei("1000000 ether")

    vault.addStrategy(strategy, deposit_limit, deposit_limit, 50, {"from": gov})

    amount0 = Wei("500 ether")
    deposit(amount0, whale, currency, vault)

    amount1 = Wei("50 ether")
    deposit(amount1, gov, currency, vault)

    strategy.harvest({"from": gov})
    sleep(chain, 30)

    vault.revokeStrategy(strategy, {"from": gov})

    # genericStateOfStrat(strategy, currency, vault)
    # genericStateOfVault(vault, currency)
    ## emergency shutdown
    strategy.harvest({"from": gov})
    strategy.harvest({"from": gov})
    assert currency.balanceOf(vault) >= amount0 + amount1
    # Emergency shut down + harvest done
    # genericStateOfStrat(strategy, currency, vault)
    # genericStateOfVault(vault, currency)


def test_apr_generic(
    strategy, web3, chain, vault, currency, whale, interface, strategist, gov
):
    dai = currency
    deposit_limit = Wei("100_000_000 ether")

    vault.addStrategy(strategy, deposit_limit, deposit_limit, 50, {"from": gov})

    deposit_amount = Wei("10_000_000 ether")
    deposit(deposit_amount, whale, currency, vault)

    # invest
    strategy.harvest({"from": gov})
    strategy.setProfitFactor(1, {"from": strategist})
    strategy.setMinCompToSell(1, {"from": gov})
    strategy.setMinWant(0, {"from": gov})

    startingBalance = vault.totalAssets()

    genericStateOfStrat(strategy, currency, vault)
    genericStateOfVault(vault, currency)

    for i in range(10):
        waitBlock = 25
        print(f"\n----wait {waitBlock} blocks----")
        sleep(chain, waitBlock)
        strategy.harvest({"from": strategist})

        profit = (vault.totalAssets() - startingBalance).to("ether")
        strState = vault.strategies(strategy)
        totalReturns = strState[6]
        totaleth = totalReturns.to("ether")
        print(f"Real Profit: {profit:.5f}")
        difff = profit - totaleth
        print(f"Diff: {difff}")

        blocks_per_year = 2_300_000
        assert startingBalance != 0
        time = (i + 1) * waitBlock
        assert time != 0
        apr = (totalReturns / startingBalance) * (blocks_per_year / time)
        print(f"implied apr: {apr:.8%}")

    vault.withdraw(vault.balanceOf(whale), {"from": whale})
