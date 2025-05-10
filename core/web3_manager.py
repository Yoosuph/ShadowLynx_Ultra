import logging
import os
from typing import Dict, Optional
from web3 import Web3, HTTPProvider
from web3.middleware import geth_poa_middleware
import config

logger = logging.getLogger(__name__)

class Web3Manager:
    """
    Manages Web3 connections to different blockchain networks
    """
    
    def __init__(self):
        """Initialize the Web3Manager"""
        self.web3_instances = {}
        self.private_key = os.environ.get("TRADING_PRIVATE_KEY")
        
        # Initialize connections
        self._initialize_connections()
        
    def _initialize_connections(self):
        """Initialize Web3 connections for configured networks"""
        for network, network_config in config.NETWORK_CONFIG.items():
            if network_config.get("enabled", False):
                self._initialize_network(network, network_config)
                
    def _initialize_network(self, network: str, network_config: Dict):
        """
        Initialize Web3 connection for a specific network
        
        Args:
            network: Network name
            network_config: Network configuration
        """
        try:
            rpc_url = network_config.get("rpc_url")
            if not rpc_url:
                logger.error(f"No RPC URL configured for {network}")
                return
                
            # Create Web3 instance
            web3 = Web3(HTTPProvider(rpc_url))
            
            # Add PoA middleware for supported networks (like BSC)
            if network in ["BSC"]:
                web3.middleware_onion.inject(geth_poa_middleware, layer=0)
                
            # Test connection
            if web3.is_connected():
                self.web3_instances[network] = web3
                block_number = web3.eth.block_number
                logger.info(f"Connected to {network} at block {block_number}")
            else:
                logger.error(f"Failed to connect to {network}")
                
        except Exception as e:
            logger.error(f"Error initializing Web3 for {network}: {str(e)}")
            
    def get_web3(self, network: str) -> Optional[Web3]:
        """
        Get Web3 instance for a specific network
        
        Args:
            network: Network name
            
        Returns:
            Web3 instance or None if not available
        """
        return self.web3_instances.get(network.upper())
        
    def is_connected(self, network: str) -> bool:
        """
        Check if connected to a specific network
        
        Args:
            network: Network name
            
        Returns:
            True if connected, False otherwise
        """
        web3 = self.get_web3(network)
        return web3 is not None and web3.is_connected()
    
    def get_gas_price(self, network: str) -> Optional[int]:
        """
        Get current gas price for a network
        
        Args:
            network: Network name
            
        Returns:
            Gas price in wei or None if error
        """
        try:
            web3 = self.get_web3(network)
            if web3 and web3.is_connected():
                return web3.eth.gas_price
            return None
        except Exception as e:
            logger.error(f"Error getting gas price for {network}: {str(e)}")
            return None
    
    def get_wallet_balance(self, network: str, address: Optional[str] = None) -> Optional[float]:
        """
        Get wallet balance in native currency
        
        Args:
            network: Network name
            address: Wallet address (uses private key wallet if None)
            
        Returns:
            Balance in native currency or None if error
        """
        try:
            web3 = self.get_web3(network)
            if not web3 or not web3.is_connected():
                return None
                
            if address is None:
                if not self.private_key:
                    logger.error("No private key provided for wallet balance check")
                    return None
                from eth_account import Account
                address = Account.from_key(self.private_key).address
                
            balance_wei = web3.eth.get_balance(Web3.toChecksumAddress(address))
            balance = web3.fromWei(balance_wei, 'ether')
            return float(balance)
            
        except Exception as e:
            logger.error(f"Error getting wallet balance for {network}: {str(e)}")
            return None
            
    def get_block_number(self, network: str) -> Optional[int]:
        """
        Get current block number for a network
        
        Args:
            network: Network name
            
        Returns:
            Current block number or None if error
        """
        try:
            web3 = self.get_web3(network)
            if web3 and web3.is_connected():
                return web3.eth.block_number
            return None
        except Exception as e:
            logger.error(f"Error getting block number for {network}: {str(e)}")
            return None

# Create a singleton instance
web3_manager = Web3Manager()