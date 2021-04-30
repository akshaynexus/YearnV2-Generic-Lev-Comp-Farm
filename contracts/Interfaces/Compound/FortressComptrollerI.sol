import "./ComptrollerI.sol";

//Since fortress renamed from we need to implement its controller funcs
interface FortressComptrollerI is ComptrollerI {
    function fortressSpeeds(address ctoken) external view returns (uint256);
    /***  FTS claims ****/
    function claimFortress(address holder) external;

    function claimFortress(address holder, CTokenI[] memory cTokens) external;
}