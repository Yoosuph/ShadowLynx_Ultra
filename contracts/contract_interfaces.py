import logging
import os
import json
from typing import Dict, List, Optional, Any
from web3 import Web3

logger = logging.getLogger(__name__)

class FlashLoanContract:
    """Interface for flash loan contracts"""
    
    def __init__(self, address: str, abi: List[Dict], web3_instance):
        """
        Initialize the flash loan contract interface
        
        Args:
            address: Contract address
            abi: Contract ABI
            web3_instance: Web3 instance
        """
        self.address = address
        self.abi = abi
        self.web3 = web3_instance
        
        # Create contract instance
        self.contract = web3_instance.eth.contract(
            address=Web3.toChecksumAddress(address),
            abi=abi
        )
        
    def get_function_signature(self, function_name: str) -> str:
        """
        Get function signature for a contract function
        
        Args:
            function_name: Name of the function
            
        Returns:
            Function signature
        """
        for item in self.abi:
            if item.get('type') == 'function' and item.get('name') == function_name:
                inputs = item.get('inputs', [])
                types = [inp.get('type') for inp in inputs]
                return f"{function_name}({','.join(types)})"
                
        return f"{function_name}()"
        
    def get_required_gas(self, function_name: str, *args) -> int:
        """
        Estimate required gas for a function call
        
        Args:
            function_name: Name of the function
            *args: Function arguments
            
        Returns:
            Estimated gas amount
        """
        try:
            # Get function from contract
            func = getattr(self.contract.functions, function_name)
            
            # Estimate gas
            return func(*args).estimateGas()
        except Exception as e:
            logger.error(f"Error estimating gas for {function_name}: {str(e)}")
            return 500000  # Default gas limit
            
    def get_contract_events(self, event_name: str, from_block: int, to_block: int = 'latest') -> List[Dict]:
        """
        Get events emitted by the contract
        
        Args:
            event_name: Name of the event
            from_block: Starting block number
            to_block: Ending block number
            
        Returns:
            List of event data dictionaries
        """
        try:
            # Get event from contract
            event = getattr(self.contract.events, event_name)
            
            # Get event logs
            logs = event.getLogs(fromBlock=from_block, toBlock=to_block)
            
            # Process logs
            events = []
            for log in logs:
                event_data = dict(log.args)
                event_data['block_number'] = log.blockNumber
                event_data['transaction_hash'] = log.transactionHash.hex()
                events.append(event_data)
                
            return events
        except Exception as e:
            logger.error(f"Error getting events for {event_name}: {str(e)}")
            return []


class FlashLoanContractFactory:
    """Factory for creating flash loan contract interfaces"""
    
    @staticmethod
    def create_contract(provider: str, network: str, web3_instance) -> Optional[FlashLoanContract]:
        """
        Create a flash loan contract interface
        
        Args:
            provider: Flash loan provider name
            network: Network name
            web3_instance: Web3 instance
            
        Returns:
            Flash loan contract interface
        """
        try:
            # Load configuration
            contract_addresses = json.loads(os.environ.get("FLASH_LOAN_CONTRACT_ADDRESSES", "{}"))
            
            # Get contract address
            address_key = f"{provider}_{network}"
            address = contract_addresses.get(address_key)
            
            if not address:
                logger.error(f"No contract address found for {address_key}")
                return None
                
            # Load ABI
            abi_key = f"{provider}_ABI"
            abi = json.loads(os.environ.get(abi_key, "[]"))
            
            if not abi:
                logger.error(f"No ABI found for {abi_key}")
                return None
                
            # Create contract interface
            return FlashLoanContract(address, abi, web3_instance)
            
        except Exception as e:
            logger.error(f"Error creating contract interface: {str(e)}")
            return None


class TokenContract:
    """Interface for ERC20 token contracts"""
    
    def __init__(self, address: str, web3_instance):
        """
        Initialize the token contract interface
        
        Args:
            address: Token contract address
            web3_instance: Web3 instance
        """
        self.address = address
        self.web3 = web3_instance
        
        # Load standard ERC20 ABI
        self.abi = json.loads(os.environ.get("ERC20_ABI", """[
            {"constant":true,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"type":"function"},
            {"constant":true,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},
            {"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},
            {"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},
            {"constant":true,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"type":"function"}
        ]"""))
        
        # Create contract instance
        self.contract = web3_instance.eth.contract(
            address=Web3.toChecksumAddress(address),
            abi=self.abi
        )
        
        # Cache for token info
        self.info_cache = {}
        
    async def get_token_info(self) -> Dict:
        """
        Get basic token information
        
        Returns:
            Dictionary with token information
        """
        if self.info_cache:
            return self.info_cache
            
        try:
            # Get token info
            name = self.contract.functions.name().call()
            symbol = self.contract.functions.symbol().call()
            decimals = self.contract.functions.decimals().call()
            total_supply = self.contract.functions.totalSupply().call()
            
            # Cache results
            self.info_cache = {
                'name': name,
                'symbol': symbol,
                'decimals': decimals,
                'total_supply': total_supply,
                'total_supply_formatted': total_supply / (10 ** decimals)
            }
            
            return self.info_cache
            
        except Exception as e:
            logger.error(f"Error getting token info for {self.address}: {str(e)}")
            
            # Return partial info if available
            if self.info_cache:
                return self.info_cache
                
            return {
                'name': 'Unknown',
                'symbol': 'UNKNOWN',
                'decimals': 18,
                'total_supply': 0,
                'total_supply_formatted': 0,
                'error': str(e)
            }
            
    async def get_balance(self, address: str) -> Dict:
        """
        Get token balance for an address
        
        Args:
            address: Address to check balance for
            
        Returns:
            Dictionary with balance information
        """
        try:
            # Get token info for decimals
            token_info = await self.get_token_info()
            
            # Get balance
            balance_wei = self.contract.functions.balanceOf(
                Web3.toChecksumAddress(address)
            ).call()
            
            # Format balance
            balance = balance_wei / (10 ** token_info['decimals'])
            
            return {
                'address': address,
                'token_address': self.address,
                'token_symbol': token_info['symbol'],
                'balance_wei': balance_wei,
                'balance': balance
            }
            
        except Exception as e:
            logger.error(f"Error getting balance for {address}: {str(e)}")
            return {
                'address': address,
                'token_address': self.address,
                'error': str(e),
                'balance_wei': 0,
                'balance': 0
            }
