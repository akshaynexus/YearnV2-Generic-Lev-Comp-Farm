import "./CErc20I.sol";

interface CTokenWithFlashloan is CErc20I {
    //Cream's custom flashloan implementation
    function flashLoan(
        address receiver,
        uint256 amount,
        bytes calldata params
    ) external;
}
