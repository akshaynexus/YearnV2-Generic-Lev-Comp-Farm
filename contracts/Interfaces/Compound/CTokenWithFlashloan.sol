import "./CErc20I.sol";

interface CTokenWithFlashloan  is CErc20I {
    //Cream's custom flashloan implementation
    function flashLoan(address receiver, uint amount, bytes calldata params) external;
}