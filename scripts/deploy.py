from pathlib import Path

from brownie import Strategy, accounts, config, network, project, web3, interface
from eth_utils import is_checksum_address


API_VERSION = config["dependencies"][0].split("@")[-1]
Vault = project.load(
    Path.home() / ".brownie" / "packages" / config["dependencies"][0]
).Vault
IVaultRegistry = interface.IVaultRegistry
WANT_TOKEN = "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56"
REGISTRY = "0x0566aea0479a837ced6c605aae81bcba18596798"

def get_address(msg: str) -> str:
    while True:
        val = input(msg)
        if is_checksum_address(val):
            return val
        else:
            addr = web3.ens.address(val)
            if addr:
                print(f"Found ENS '{val}' [{addr}]")
                return addr
        print(f"I'm sorry, but '{val}' is not a checksummed address or ENS")


def main():
    print(f"You are using the '{network.show_active()}' network")
    dev = accounts.load("dev")
    print(f"You are using: 'dev' [{dev.address}]")

    if input("Is there a Vault for this strategy already? y/[N]: ").lower() == "y":
        vault = Vault.at(get_address("Deployed Vault: "))
        assert vault.apiVersion() == API_VERSION
    else:
        vaultRegistry = IVaultRegistry(REGISTRY)
        # Deploy and get Vault deployment address
        expVaultTx = vaultRegistry.newExperimentalVault(
            WANT_TOKEN,
            dev.address,
            dev.address,
            dev.address,
            "",
            "",
            {"from": dev},
        )
        vault = Vault.at(expVaultTx.return_value)

    print(
        f"""
    Strategy Parameters

       api: {API_VERSION}
     token: {vault.token()}
      name: '{vault.name()}'
    symbol: '{vault.symbol()}'
    """
    )
    if input("Deploy Strategy? y/[N]: ").lower() != "y":
        return
    fbusd = "0x8BB0d002bAc7F1845cB2F14fe3D6Aae1D1601e29"
    crBUSD = "0x2Bc4eb013DDee29D37920938B96d353171289B7C"

    strategy = Strategy.deploy(vault,fbusd, crBUSD, {"from": dev},publish_source=True)
