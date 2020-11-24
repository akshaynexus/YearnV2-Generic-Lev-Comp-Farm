// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.6.12;

pragma experimental ABIEncoderV2;

import "@yearnvaults/contracts/BaseStrategy.sol";

import "./Interfaces/DyDx/DydxFlashLoanBase.sol";
import "./Interfaces/DyDx/ICallee.sol";

import "./Interfaces/Aave/FlashLoanReceiverBase.sol";
import "./Interfaces/Aave/ILendingPoolAddressesProvider.sol";
import "./Interfaces/Aave/ILendingPool.sol";

import "@openzeppelinV3/contracts/token/ERC20/IERC20.sol";
import "@openzeppelinV3/contracts/math/SafeMath.sol";
import "@openzeppelinV3/contracts/math/Math.sol";
import "@openzeppelinV3/contracts/utils/Address.sol";
import "@openzeppelinV3/contracts/token/ERC20/SafeERC20.sol";

import "./Interfaces/UniswapInterfaces/IUniswapV2Router02.sol";

import "./Interfaces/Chainlink/AggregatorV3Interface.sol";

import "./Interfaces/Compound/CErc20I.sol";
import "./Interfaces/Compound/ComptrollerI.sol";

/********************
 *   A lender optimisation strategy for any erc20 asset
 *   Made by SamPriestley.com
 *   https://github.com/Grandthrax/yearnV2-generic-lender-strat
 *   v0.2.0
 *
 ********************* */

contract Strategy is BaseStrategy, DydxFlashloanBase, ICallee, FlashLoanReceiverBase {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    // @notice emitted when trying to do Flash Loan. flashLoan address is 0x00 when no flash loan used
    event Leverage(uint256 amountRequested, uint256 amountGiven, bool deficit, address flashLoan);

    //Flash Loan Providers
    address private constant SOLO = 0x1E0447b19BB6EcFdAe1e4AE1694b0C3659614e4e;
    address private constant AAVE_LENDING = 0x24a42fD28C976A61Df5D00D0599C34c4f90748c8;

    // Chainlink price feed contracts
    address private constant COMP2USD = 0xdbd020CAeF83eFd542f4De03e3cF0C28A4428bd5;
    address private constant DAI2USD = 0xAed0c38402a5d19df6E4c03F4E2DceD6e29c1ee9;
    address private constant ETH2USD = 0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419;

    // Comptroller address for compound.finance
    ComptrollerI public constant compound = ComptrollerI(0x3d9819210A31b4961b30EF54bE2aeD79B9c9Cd3B);

    //Only three tokens we use
    address public constant comp = address(0xc00e94Cb662C3520282E6f5717214004A7f26888);
    CErc20I public cToken;
    //address public constant DAI = address(0x6B175474E89094C44Da98b954EedeAC495271d0F);

    address public constant uniswapRouter = address(0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D);
    address public constant weth = address(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2);

    //Operating variables
    uint256 public collateralTarget = 0.73 ether; // 73%
    uint256 public blocksToLiquidationDangerZone = 46500; // 7 days =  60*60*24*7/13

    uint256 public minWant = 10 ether; //Only lend if we have enough want to be worth it
    uint256 public minCompToSell = 0.5 ether; //used both as the threshold to sell but also as a trigger for harvest
    uint256 public gasFactor = 50; // multiple before triggering harvest

    //To deactivate flash loan provider if needed
    bool public DyDxActive = true;
    bool public AaveActive = true;
    bool public leverageActived = true;

    constructor(address _vault, string memory name, address _cToken) public BaseStrategy(_vault) FlashLoanReceiverBase(AAVE_LENDING) {
        cToken = CErc20I(address(_cToken));

        //pre-set approvals
        IERC20(comp).safeApprove(uniswapRouter, uint256(-1));
        want.safeApprove(address(cToken), uint256(-1));
        want.safeApprove(SOLO, uint256(-1));


        // You can set these parameters on deployment to whatever you want
        minReportDelay = 6300;
        profitFactor = 100;
        debtThreshold = 1000;


        //we do this horrible thing because you can't compare strings in solidity
        require(keccak256(bytes(apiVersion())) == keccak256(bytes(VaultAPI(_vault).apiVersion())), "WRONG VERSION");
    }

    function name() external override pure returns (string memory){
        return "GenericLevCompFarm";
    }

    /*
     * Control Functions
     */
    function setDyDx(bool _dydx) external {
        require(msg.sender == governance() || msg.sender == strategist, "!management"); // dev: not governance or strategist
        DyDxActive = _dydx;
    }
    function setAave(bool _ave) external {
        require(msg.sender == governance() || msg.sender == strategist, "!management"); // dev: not governance or strategist
        AaveActive = _ave;
    }

    function setLeverage(bool _lev) external {
        require(msg.sender == governance() || msg.sender == strategist, "!management"); // dev: not governance or strategist
        leverageActived = _lev;
    }

    function setGasFactor(uint256 _gasFactor) external {
        require(msg.sender == governance() || msg.sender == strategist, "!management"); // dev: not governance or strategist
        gasFactor = _gasFactor;
    }

    function setMinCompToSell(uint256 _minCompToSell) external {
        require(msg.sender == governance() || msg.sender == strategist, "!management"); // dev: not governance or strategist
        minCompToSell = _minCompToSell;
    }

    function setCollateralTarget(uint256 _collateralTarget) external {
        require(msg.sender == governance() || msg.sender == strategist, "!management"); // dev: not governance or strategist
        collateralTarget = _collateralTarget;
    }


    
    /*
     * Base External Facing Functions
     */

    /*
     * Expected return this strategy would provide to the Vault the next time `report()` is called
     *
     * The total assets currently in strategy minus what vault believes we have
     * Does not include unrealised profit such as comp.
     */
    function expectedReturn() public view returns (uint256) {
        uint256 estimateAssets = estimatedTotalAssets();

        uint256 debt = vault.strategies(address(this)).totalDebt;
        if (debt > estimateAssets) {
            return 0;
        } else {
            return estimateAssets - debt;
        }
    }

    /*
     * An accurate estimate for the total amount of assets (principle + return)
     * that this strategy is currently managing, denominated in terms of want tokens.
     */
    function estimatedTotalAssets() public override view returns (uint256) {
        (uint256 deposits, uint256 borrows) = getCurrentPosition();

        uint256 _claimableComp = predictCompAccrued();
        uint256 currentComp = IERC20(comp).balanceOf(address(this));

        // Use chainlink price feed to retrieve COMP and want prices expressed in USD. Then convert
        uint256 latestExchangeRate = getLatestExchangeRate();

        uint256 estimatedDAI = latestExchangeRate.mul(_claimableComp.add(currentComp));
        uint256 conservativeDai = estimatedDAI.mul(9).div(10); //10% pessimist

        return want.balanceOf(address(this)).add(deposits).add(conservativeDai).sub(borrows);
    }

    /*
     * Aggragate the value in USD for COMP and want onchain from different chainlink nodes
     * reducing risk of price manipulation within onchain market.
     * Operation: COMP_PRICE_IN_USD / DAI_PRICE_IN_USD
     */
    function getLatestExchangeRate() public view returns (uint256) {
        (, uint256 price_comp, , , ) = AggregatorV3Interface(COMP2USD).latestRoundData();
        (, uint256 price_dai, , , ) = AggregatorV3Interface(DAI2USD).latestRoundData();

        return price_comp.mul(1 ether).div(price_dai).div(1 ether);
    }

    function getCompValInWei(uint256 _amount) public view returns (uint256) {
        (, uint256 price_comp, , , ) = AggregatorV3Interface(COMP2USD).latestRoundData();
        (, uint256 price_eth, , , ) = AggregatorV3Interface(ETH2USD).latestRoundData();

        return price_comp.mul(1 ether).div(price_eth).mul(_amount).div(1 ether);
    }

    /*
     * Provide a signal to the keeper that `tend()` should be called.
     * (keepers are always reimbursed by yEarn)
     *
     * NOTE: this call and `harvestTrigger` should never return `true` at the same time.
     */
    function tendTrigger(uint256 gasCost) public override view returns (bool) {
        if (harvestTrigger(0)) {
            //harvest takes priority
            return false;
        }

        if (getblocksUntilLiquidation() <= blocksToLiquidationDangerZone) {
            return true;
        }
    }

    /*
     * Provide a signal to the keeper that `harvest()` should be called.
     * gasCost is expected_gas_use * gas_price
     * (keepers are always reimbursed by yEarn)
     *
     * NOTE: this call and `tendTrigger` should never return `true` at the same time.
     */
    function harvestTrigger(uint256 gasCost) public override view returns (bool) {
        if (vault.creditAvailable() > minWant.mul(gasFactor)) {
            return true;
        }

        // after enough comp has accrued we want the bot to run
        uint256 _claimableComp = predictCompAccrued();

        if (_claimableComp > minCompToSell) {
            // check value of COMP in wei
            uint256 _compWei = getCompValInWei(_claimableComp.add(IERC20(comp).balanceOf(address(this))));
            if (_compWei > gasCost.mul(gasFactor)) {
                return true;
            }
        }

        return false;
    }

    /*****************
     * Public non-base function
     ******************/

    //Calculate how many blocks until we are in liquidation based on current interest rates
    //WARNING does not include compounding so the estimate becomes more innacurate the further ahead we look
    //equation. Compound doesn't include compounding for most blocks
    //((deposits*colateralThreshold - borrows) / (borrows*borrowrate - deposits*colateralThreshold*interestrate));
    function getblocksUntilLiquidation() public view returns (uint256 blocks) {
        (, uint256 collateralFactorMantissa, ) = compound.markets(address(cToken));

        (uint256 deposits, uint256 borrows) = getCurrentPosition();

        uint256 borrrowRate = cToken.borrowRatePerBlock();

        uint256 supplyRate = cToken.supplyRatePerBlock();

        uint256 collateralisedDeposit1 = deposits.mul(collateralFactorMantissa);
        uint256 collateralisedDeposit = collateralisedDeposit1.div(1e18);

        uint256 denom1 = borrows.mul(borrrowRate);
        uint256 denom2 = collateralisedDeposit.mul(supplyRate);

        if (denom2 >= denom1) {
            blocks = uint256(-1);
        } else {
            uint256 numer = collateralisedDeposit.sub(borrows);
            uint256 denom = denom1 - denom2;

            blocks = numer.mul(1e18).div(denom);
        }
    }

    // This function makes a prediction on how much comp is accrued
    // It is not 100% accurate as it uses current balances in Compound to predict into the past
    function predictCompAccrued() public view returns (uint256) {
        (uint256 deposits, uint256 borrows) = getCurrentPosition();
        if (deposits == 0) {
            return 0; // should be impossible to have 0 balance and positive comp accrued
        }

        //comp speed is amount to borrow or deposit (so half the total distribution for want)
        uint256 distributionPerBlock = compound.compSpeeds(address(cToken));

        uint256 totalBorrow = cToken.totalBorrows();

        //total supply needs to be echanged to underlying using exchange rate
        uint256 totalSupplyCtoken = cToken.totalSupply();
        uint256 totalSupply = totalSupplyCtoken.mul(cToken.exchangeRateStored()).div(1e18);

        uint256 blockShareSupply = deposits.mul(distributionPerBlock).div(totalSupply);
        uint256 blockShareBorrow = borrows.mul(distributionPerBlock).div(totalBorrow);

        //how much we expect to earn per block
        uint256 blockShare = blockShareSupply.add(blockShareBorrow);

        //last time we ran harvest
        uint256 lastReport = vault.strategies(address(this)).lastReport;
        uint256 blocksSinceLast= (block.timestamp.sub(lastReport)).div(13); //roughly 13 seconds per block

        return blocksSinceLast.mul(blockShare);
    }

    //Returns the current position
    //WARNING - this returns just the balance at last time someone touched the cToken token. Does not accrue interst in between
    //cToken is very active so not normally an issue.
    function getCurrentPosition() public view returns (uint256 deposits, uint256 borrows) {
        (, uint256 ctokenBalance, uint256 borrowBalance, uint256 exchangeRate) = cToken.getAccountSnapshot(address(this));
        borrows = borrowBalance;

        deposits = ctokenBalance.mul(exchangeRate).div(1e18);
    }

    //statechanging version
    function getLivePosition() public returns (uint256 deposits, uint256 borrows) {
        deposits = cToken.balanceOfUnderlying(address(this));

        //we can use non state changing now because we updated state with balanceOfUnderlying call
        borrows = cToken.borrowBalanceStored(address(this));
    }

    //Same warning as above
    function netBalanceLent() public view returns (uint256) {
        (uint256 deposits, uint256 borrows) = getCurrentPosition();
        return deposits.sub(borrows);
    }

    /***********
     * internal core logic
     *********** */
    /*
     * A core method.
     * Called at beggining of harvest before providing report to owner
     * 1 - claim accrued comp
     * 2 - if enough to be worth it we sell
     * 3 - because we lose money on our loans we need to offset profit from comp.
     */
    function prepareReturn(uint256 _debtOutstanding)
        internal
        override
        returns (
            uint256 _profit,
            uint256 _loss,
            uint256 _debtPayment
        ) {

        _profit = 0;
        _loss = 0; //for clarity

        if (cToken.balanceOf(address(this)) == 0) {
            uint256 wantBalance = want.balanceOf(address(this));
            //no position to harvest
            //but we may have some debt to return
            //it is too expensive to free more debt in this method so we do it in adjust position
            _debtPayment = Math.min(wantBalance, _debtOutstanding); 
            return (_profit, _loss, _debtPayment);
        }

        //claim comp accrued
        _claimComp();
        //sell comp
        _disposeOfComp();

        uint256 wantBalance = want.balanceOf(address(this));

        //we did state change in claimcomp so this is safe
        uint256 investedBalance = netBalanceLent();
        uint256 balance = investedBalance.add(wantBalance);

        uint256 debt = vault.strategies(address(this)).totalDebt;

        //Balance - Total Debt is profit
        if (balance > debt) {
            _profit = balance - debt;

            if (wantBalance < _profit) {
                //all reserve is profit
                _profit = wantBalance;
            } else if (wantBalance > _profit.add(_debtOutstanding)){
                _debtPayment = _debtOutstanding;
            }else{
                _debtPayment = wantBalance - _profit;
            }
        } else {
            //we will lose money until we claim comp then we will make money
            //this has an unintended side effect of slowly lowering our total debt allowed
            _loss = debt - balance;
            _debtPayment = Math.min(wantBalance, _debtOutstanding);
        }
    }

    /*
     * Second core function. Happens after report call.
     *
     * Similar to deposit function from V1 strategy
     */

    function adjustPosition(uint256 _debtOutstanding) internal override {
        //emergency exit is dealt with in prepareReturn
        if (emergencyExit) {
            return;
        }

        //we are spending all our cash unless we have debt outstanding
        uint256 _wantBal = want.balanceOf(address(this));
        if(_wantBal < _debtOutstanding){
            //this is graceful withdrawal. dont use backup
            //we use more than 1 because withdraw underlying causes problems with 1 token
            if(cToken.balanceOf(address(this)) > 1){ 
                _withdrawSome(_debtOutstanding - _wantBal, false);
            }

            return;
        }
        

        (uint256 position, bool deficit) = _calculateDesiredPosition(_wantBal - _debtOutstanding, true);

        
        //if we are below minimun want change it is not worth doing
        //need to be careful in case this pushes to liquidation
        if (position > minWant) {
            //if dydx is not active we just try our best with basic leverage
            if (!DyDxActive) {
                _noFlashLoan(position, deficit);
            } else {
                //if there is huge position to improve we want to do normal leverage. it is quicker
                if (position > want.balanceOf(SOLO)) {
                    position = position.sub(_noFlashLoan(position, deficit));
                }

                //flash loan to position
                doDyDxFlashLoan(deficit, position);
            }
        }
    }

    /*************
     * Very important function
     * Input: amount we want to withdraw and whether we are happy to pay extra for Aave.
     *       cannot be more than we have
     * Returns amount we were able to withdraw. notall if user has some balance left
     *
     * Deleverage position -> redeem our cTokens
     ******************** */
    function _withdrawSome(uint256 _amount, bool _useBackup) internal returns (bool notAll) {
        (uint256 position, bool deficit) = _calculateDesiredPosition(_amount, false);

        //If there is no deficit we dont need to adjust position
        if (deficit) {
            //we do a flash loan to give us a big gap. from here on out it is cheaper to use normal deleverage. Use Aave for extremely large loans
            if (DyDxActive) {
                position = position.sub(doDyDxFlashLoan(deficit, position));
            }

            // Will decrease number of interactions using aave as backup
            // because of fee we only use in emergency
            if (position > 0 && AaveActive && _useBackup) {
                position = position.sub(doAaveFlashLoan(deficit, position));
            }

            uint8 i = 0;
            //position will equal 0 unless we haven't been able to deleverage enough with flash loan
            //if we are not in deficit we dont need to do flash loan
            while (position > 0) {
                position = position.sub(_noFlashLoan(position, true));
                i++;

                //A limit set so we don't run out of gas
                if (i >= 5) {
                    notAll = true;
                    break;
                }
            }
        }

        //now withdraw
        //if we want too much we just take max

        //This part makes sure our withdrawal does not force us into liquidation
        (uint256 depositBalance, uint256 borrowBalance) = getCurrentPosition();

        uint256 AmountNeeded = borrowBalance.mul(1e18).div(collateralTarget);
        uint256 redeemable = depositBalance.sub(AmountNeeded);

        if (redeemable < _amount) {
            cToken.redeemUnderlying(redeemable);
        } else {
            cToken.redeemUnderlying(_amount);
        }

        //let's sell some comp if we have more than needed
        //flash loan would have sent us comp if we had some accrued so we don't need to call claim comp
        _disposeOfComp();
    }

    /***********
     *  This is the main logic for calculating how to change our lends and borrows
     *  Input: balance. The net amount we are going to deposit/withdraw.
     *  Input: dep. Is it a deposit or withdrawal
     *  Output: position. The amount we want to change our current borrow position.
     *  Output: deficit. True if we are reducing position size
     *
     *  For instance deficit =false, position 100 means increase borrowed balance by 100
     ****** */
    function _calculateDesiredPosition(uint256 balance, bool dep) internal returns (uint256 position, bool deficit) {
        //we want to use statechanging for safety
        (uint256 deposits, uint256 borrows) = getLivePosition();

        //When we unwind we end up with the difference between borrow and supply
        uint256 unwoundDeposit = deposits.sub(borrows);

        //we want to see how close to collateral target we are.
        //So we take our unwound deposits and add or remove the balance we are are adding/removing.
        //This gives us our desired future undwoundDeposit (desired supply)

        uint256 desiredSupply = 0;
        if (dep) {
            desiredSupply = unwoundDeposit.add(balance);
        } else { 
            if(balance > unwoundDeposit) balance = unwoundDeposit;
            desiredSupply = unwoundDeposit.sub(balance);
        }

        //(ds *c)/(1-c)
        uint256 num = desiredSupply.mul(collateralTarget);
        uint256 den = uint256(1e18).sub(collateralTarget);

        uint256 desiredBorrow = num.div(den);
        if (desiredBorrow > 1e18) {
            //stop us going right up to the wire
            desiredBorrow = desiredBorrow - 1e18;
        }

        //now we see if we want to add or remove balance
        // if the desired borrow is less than our current borrow we are in deficit. so we want to reduce position
        if (desiredBorrow < borrows) {
            deficit = true;
            position = borrows - desiredBorrow; //safemath check done in if statement
        } else {
            //otherwise we want to increase position
            deficit = false;
            position = desiredBorrow - borrows;
        }
    }

    /*
     * Liquidate as many assets as possible to `want`, irregardless of slippage,
     * up to `_amount`. Any excess should be re-invested here as well.
     */
    function liquidatePosition(uint256 _amountNeeded) internal override returns (uint256 _amountFreed) {
        uint256 _balance = want.balanceOf(address(this));

        if (netBalanceLent().add(_balance) < _amountNeeded) {
            //if we cant afford to withdraw we take all we can
            //withdraw all we can
            (,_amountFreed) = exitPosition();
        } else {
            if (_balance < _amountNeeded) {
                _withdrawSome(_amountNeeded.sub(_balance), true);
                _amountFreed = want.balanceOf(address(this));
            }else{
                _amountFreed = _balance - _amountNeeded;
            }
        }
    }

    function _claimComp() public {
        CTokenI[] memory tokens = new CTokenI[](1);
        tokens[0] = cToken;

        compound.claimComp(address(this), tokens);
    }

    //sell comp function
    function _disposeOfComp() internal {
        uint256 _comp = IERC20(comp).balanceOf(address(this));

        if (_comp > minCompToSell) {
            address[] memory path = new address[](3);
            path[0] = comp;
            path[1] = weth;
            path[2] = address(want);

            IUniswapV2Router02(uniswapRouter).swapExactTokensForTokens(_comp, uint256(0), path, address(this), now);
        }
    }

    /*
     * Make as much capital as possible "free" for the Vault to take. Some slippage
     * is allowed.
     */
    function exitPosition() internal override returns (uint256 _loss, uint256 _debtPayment){
        uint256 balanceBefore = vault.strategies(address(this)).totalDebt;

        //we dont use getCurrentPosition() because it won't be exact
        (uint256 deposits, uint256 borrows) = getLivePosition();
        _withdrawSome(deposits.sub(borrows), true);
        _debtPayment = want.balanceOf(address(this));
        if(balanceBefore > _debtPayment){
            _loss = balanceBefore - _debtPayment;
        }
    }

    //lets leave
    function prepareMigration(address _newStrategy) internal override {
        (uint256 deposits, uint256 borrows) = getLivePosition();
        _withdrawSome(deposits.sub(borrows), false);

        (, , uint256 borrowBalance, ) = cToken.getAccountSnapshot(address(this));

        require(borrowBalance == 0, "DELEVERAGE_FIRST");

        want.safeTransfer(_newStrategy, want.balanceOf(address(this)));

        cToken.transfer(_newStrategy, cToken.balanceOf(address(this)));

        IERC20 _comp = IERC20(comp);
        _comp.safeTransfer(_newStrategy, _comp.balanceOf(address(this)));
    }

    //Three functions covering normal leverage and deleverage situations
    // max is the max amount we want to increase our borrowed balance
    // returns the amount we actually did
    function _noFlashLoan(uint256 max, bool deficit) internal returns (uint256 amount) {
        //we can use non-state changing because this function is always called after _calculateDesiredPosition
        (uint256 lent, uint256 borrowed) = getCurrentPosition();

        if (borrowed == 0) {
            return 0;
        }

        (, uint256 collateralFactorMantissa, ) = compound.markets(address(cToken));

        if (deficit) {
            amount = _normalDeleverage(max, lent, borrowed, collateralFactorMantissa);
        } else {
            amount = _normalLeverage(max, lent, borrowed, collateralFactorMantissa);
        }

        emit Leverage(max, amount, deficit, address(0));
    }

    //maxDeleverage is how much we want to reduce by
    function _normalDeleverage(
        uint256 maxDeleverage,
        uint256 lent,
        uint256 borrowed,
        uint256 collatRatio
    ) internal returns (uint256 deleveragedAmount) {
        uint256 theoreticalLent = borrowed.mul(1e18).div(collatRatio);

        deleveragedAmount = lent.sub(theoreticalLent);

        if (deleveragedAmount >= borrowed) {
            deleveragedAmount = borrowed;
        }
        if (deleveragedAmount >= maxDeleverage) {
            deleveragedAmount = maxDeleverage;
        }

        cToken.redeemUnderlying(deleveragedAmount);

        //our borrow has been increased by no more than maxDeleverage
        cToken.repayBorrow(deleveragedAmount);
    }

    //maxDeleverage is how much we want to increase by
    function _normalLeverage(
        uint256 maxLeverage,
        uint256 lent,
        uint256 borrowed,
        uint256 collatRatio
    ) internal returns (uint256 leveragedAmount) {
        uint256 theoreticalBorrow = lent.mul(collatRatio).div(1e18);

        leveragedAmount = theoreticalBorrow.sub(borrowed);

        if (leveragedAmount >= maxLeverage) {
            leveragedAmount = maxLeverage;
        }

        cToken.borrow(leveragedAmount);
        cToken.mint(want.balanceOf(address(this)));
    }

    //called by flash loan
    function _loanLogic(
        bool deficit,
        uint256 amount,
        uint256 repayAmount
    ) internal {
        uint256 bal = want.balanceOf(address(this));
        require(bal >= amount, "FLASH_FAILED"); // to stop malicious calls

        //if in deficit we repay amount and then withdraw
        if (deficit) {
            cToken.repayBorrow(amount);

            //if we are withdrawing we take more to cover fee
            cToken.redeemUnderlying(repayAmount);
        } else {
            require(cToken.mint(bal) == 0, "mint error");

            //borrow more to cover fee
            // fee is so low for dydx that it does not effect our liquidation risk.
            //DONT USE FOR AAVE
            cToken.borrow(repayAmount);
        }
    }

    function protectedTokens() internal override view returns (address[] memory) {
        address[] memory protected = new address[](3);
        protected[0] = address(want);
        protected[1] = comp;
        protected[2] = address(cToken);
        return protected;
    }

    /******************
     * Flash loan stuff
     ****************/

    // Flash loan DXDY
    // amount desired is how much we are willing for position to change
    function doDyDxFlashLoan(bool deficit, uint256 amountDesired) internal returns (uint256) {
        uint256 amount = amountDesired;
        ISoloMargin solo = ISoloMargin(SOLO);
        uint256 marketId = _getMarketIdFromTokenAddress(SOLO, address(want));

        // Not enough want in DyDx. So we take all we can
        uint256 amountInSolo = want.balanceOf(SOLO);

        if (amountInSolo < amount) {
            amount = amountInSolo;
        }

        uint256 repayAmount = amount.add(2); // we need to overcollateralise on way back

        bytes memory data = abi.encode(deficit, amount, repayAmount);

        // 1. Withdraw $
        // 2. Call callFunction(...)
        // 3. Deposit back $
        Actions.ActionArgs[] memory operations = new Actions.ActionArgs[](3);

        operations[0] = _getWithdrawAction(marketId, amount);
        operations[1] = _getCallAction(
            // Encode custom data for callFunction
            data
        );
        operations[2] = _getDepositAction(marketId, repayAmount);

        Account.Info[] memory accountInfos = new Account.Info[](1);
        accountInfos[0] = _getAccountInfo();

        solo.operate(accountInfos, operations);

        emit Leverage(amountDesired, amount, deficit, SOLO);

        return amount;
    }

    //returns our current collateralisation ratio. Should be compared with collateralTarget
    function storedCollateralisation() public view returns (uint256 collat) {
        (uint256 lend, uint256 borrow) = getCurrentPosition();
        if (lend == 0) {
            return 0;
        }
        collat = uint256(1e18).mul(borrow).div(lend);
    }

    //DyDx calls this function after doing flash loan
    function callFunction(
        address sender,
        Account.Info memory account,
        bytes memory data
    ) public override {
        (bool deficit, uint256 amount, uint256 repayAmount) = abi.decode(data, (bool, uint256, uint256));

        _loanLogic(deficit, amount, repayAmount);
    }

    function doAaveFlashLoan(bool deficit, uint256 _flashBackUpAmount) public returns (uint256 amount) {
        //we do not want to do aave flash loans for leveraging up. Fee could put us into liquidation
        if (!deficit) {
            return _flashBackUpAmount;
        }

        ILendingPool lendingPool = ILendingPool(addressesProvider.getLendingPool());

        uint256 availableLiquidity = want.balanceOf(address(0x3dfd23A6c5E8BbcFc9581d2E864a68feb6a076d3));

        if (availableLiquidity < _flashBackUpAmount) {
            amount = availableLiquidity;
        } else {
            amount = _flashBackUpAmount;
        }

        require(amount <= _flashBackUpAmount); // dev: "incorrect amount"

        bytes memory data = abi.encode(deficit, amount);

        lendingPool.flashLoan(address(this), address(want), amount, data);

        emit Leverage(_flashBackUpAmount, amount, deficit, AAVE_LENDING);
    }

    //Aave calls this function after doing flash loan
    function executeOperation(
        address _reserve,
        uint256 _amount,
        uint256 _fee,
        bytes calldata _params
    ) external override {
        (bool deficit, uint256 amount) = abi.decode(_params, (bool, uint256));

        _loanLogic(deficit, amount, amount.add(_fee));

        // return the flash loan plus Aave's flash loan fee back to the lending pool
        uint256 totalDebt = _amount.add(_fee);
        transferFundsBackToPoolInternal(_reserve, totalDebt);
    }
}
