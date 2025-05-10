import logging
import asyncio
from typing import Dict, List, Optional, Any
import config
from dexs.dex_interfaces import create_dex_interface, DEXInterface
from core.web3_manager import web3_manager

logger = logging.getLogger(__name__)

class DEXManager:
    """
    Manages DEX interfaces and provides unified access to price data
    """
    
    def __init__(self):
        """Initialize the DEXManager"""
        self.dex_interfaces = {}
        self._initialize_dexs()
        
    def _initialize_dexs(self):
        """Initialize DEX interfaces for all configured networks and DEXs"""
        for network, network_config in config.NETWORK_CONFIG.items():
            if not network_config.get("enabled", False):
                continue
                
            web3_instance = web3_manager.get_web3(network)
            if not web3_instance:
                logger.warning(f"No Web3 instance for {network}, skipping DEX initialization")
                continue
                
            # Get enabled DEXs for this network
            enabled_dexs = config.get_enabled_dexes(network)
            
            for dex_name in enabled_dexs:
                try:
                    dex_interface = create_dex_interface(dex_name, network, web3_instance)
                    
                    key = f"{dex_name}_{network}"
                    self.dex_interfaces[key] = dex_interface
                    
                    logger.info(f"Initialized {dex_name} interface for {network}")
                except Exception as e:
                    logger.error(f"Error initializing {dex_name} for {network}: {str(e)}")
                    
    def get_dex_interface(self, dex_name: str, network: str) -> Optional[DEXInterface]:
        """
        Get DEX interface for a specific DEX and network
        
        Args:
            dex_name: DEX name
            network: Network name
            
        Returns:
            DEX interface or None if not available
        """
        key = f"{dex_name}_{network}"
        return self.dex_interfaces.get(key)
        
    async def get_price(self, token_pair: str, dex_name: str, network: str) -> Optional[Dict]:
        """
        Get price data for a token pair from a specific DEX
        
        Args:
            token_pair: Token pair (e.g., "ETH-USDT")
            dex_name: DEX name
            network: Network name
            
        Returns:
            Price data dictionary or None if failed
        """
        dex_interface = self.get_dex_interface(dex_name, network)
        if not dex_interface:
            logger.warning(f"No interface found for {dex_name} on {network}")
            return None
            
        return await dex_interface.get_price(token_pair)
        
    async def get_liquidity(self, token_pair: str, dex_name: str, network: str) -> Optional[float]:
        """
        Get liquidity data for a token pair from a specific DEX
        
        Args:
            token_pair: Token pair (e.g., "ETH-USDT")
            dex_name: DEX name
            network: Network name
            
        Returns:
            Liquidity in USD or None if failed
        """
        dex_interface = self.get_dex_interface(dex_name, network)
        if not dex_interface:
            logger.warning(f"No interface found for {dex_name} on {network}")
            return None
            
        return await dex_interface.get_liquidity(token_pair)
        
    async def get_all_prices(self, token_pair: str) -> List[Dict]:
        """
        Get price data for a token pair from all available DEXs
        
        Args:
            token_pair: Token pair (e.g., "ETH-USDT")
            
        Returns:
            List of price data dictionaries
        """
        tasks = []
        
        for key, dex_interface in self.dex_interfaces.items():
            dex_name, network = key.split('_')
            task = asyncio.create_task(dex_interface.get_price(token_pair))
            tasks.append((dex_name, network, task))
            
        results = []
        
        for dex_name, network, task in tasks:
            try:
                price_data = await task
                if price_data:
                    price_data['dex_name'] = dex_name
                    results.append(price_data)
            except Exception as e:
                logger.error(f"Error getting price from {dex_name} on {network}: {str(e)}")
                
        return results
        
    def get_supported_token_pairs(self) -> List[str]:
        """
        Get list of supported token pairs
        
        Returns:
            List of token pairs
        """
        return config.TRADING_CONFIG.get("token_pairs", [])
        
    def get_available_dexs(self) -> Dict[str, List[str]]:
        """
        Get mapping of networks to available DEXs
        
        Returns:
            Dictionary mapping networks to lists of available DEXs
        """
        result = {}
        
        for key in self.dex_interfaces:
            dex_name, network = key.split('_')
            
            if network not in result:
                result[network] = []
                
            result[network].append(dex_name)
            
        return result

# Create a singleton instance
dex_manager = DEXManager()