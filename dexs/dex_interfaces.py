import logging
import asyncio
import aiohttp
import json
import os
from typing import Dict, List, Optional, Any
from web3 import Web3
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class DEXInterface(ABC):
    """Base class for DEX interfaces"""
    
    def __init__(self, network: str, web3_instance):
        """
        Initialize the DEX interface
        
        Args:
            network: Network name (BSC or POLYGON)
            web3_instance: Web3 instance for the network
        """
        self.network = network
        self.web3 = web3_instance
        
        # Default API rate limiting
        self.min_api_interval = 0.5  # seconds between API calls
        
    @abstractmethod
    async def get_price(self, token_pair: str) -> Optional[Dict]:
        """
        Get price data for a token pair
        
        Args:
            token_pair: Token pair (e.g., "ETH-USDT")
            
        Returns:
            Price data dictionary or None if failed
        """
        pass
        
    @abstractmethod
    async def get_liquidity(self, token_pair: str) -> Optional[float]:
        """
        Get liquidity data for a token pair
        
        Args:
            token_pair: Token pair (e.g., "ETH-USDT")
            
        Returns:
            Liquidity in USD or None if failed
        """
        pass
        
    def format_result(self, token_pair: str, price: float, liquidity: float = None) -> Dict:
        """
        Format price data result
        
        Args:
            token_pair: Token pair (e.g., "ETH-USDT")
            price: Token price
            liquidity: Optional liquidity in USD
            
        Returns:
            Formatted price data dictionary
        """
        result = {
            'token_pair': token_pair,
            'price': price,
            'network': self.network
        }
        
        if liquidity is not None:
            result['liquidity'] = liquidity
            
        return result
        

class PancakeSwapInterface(DEXInterface):
    """Interface for PancakeSwap DEX"""
    
    def __init__(self, network: str, web3_instance):
        super().__init__(network, web3_instance)
        
        # PancakeSwap specific settings
        self.api_url = "https://api.pancakeswap.info/api/v2"
        self.min_api_interval = 1.0  # PancakeSwap API is rate limited
        
        # Load contract addresses
        self.load_contract_addresses()
        
    def load_contract_addresses(self):
        """Load contract addresses for PancakeSwap"""
        # Router contract addresses
        if self.network == 'BSC':
            self.router_address = os.environ.get(
                "PANCAKESWAP_ROUTER_BSC", 
                "0x10ED43C718714eb63d5aA57B78B54704E256024E"
            )
        else:
            # PancakeSwap isn't on Polygon, but we'll set a placeholder
            self.router_address = None
            
        # Factory contract addresses for getting pairs
        if self.network == 'BSC':
            self.factory_address = os.environ.get(
                "PANCAKESWAP_FACTORY_BSC",
                "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
            )
        else:
            self.factory_address = None
            
    async def get_price(self, token_pair: str) -> Optional[Dict]:
        """
        Get price data for a token pair from PancakeSwap
        
        Args:
            token_pair: Token pair (e.g., "ETH-USDT")
            
        Returns:
            Price data dictionary or None if failed
        """
        if self.network != 'BSC':
            logger.warning("PancakeSwap is only available on BSC network")
            return None
            
        try:
            # Parse token pair
            tokens = token_pair.split('-')
            if len(tokens) != 2:
                logger.warning(f"Invalid token pair format: {token_pair}")
                return None
                
            token_a, token_b = tokens
            
            # Try to get price from API first
            async with aiohttp.ClientSession() as session:
                # Use API to get price
                token_addresses = json.loads(os.environ.get("TOKEN_ADDRESSES", "{}"))
                token_a_address = token_addresses.get(f"{token_a}_BSC")
                
                if not token_a_address:
                    logger.warning(f"Token address not found for {token_a} on BSC")
                    return None
                    
                # Attempt to get token data from PancakeSwap API
                async with session.get(f"{self.api_url}/tokens/{token_a_address}") as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'data' in data:
                            price = float(data['data']['price'])
                            liquidity_usd = float(data['data'].get('liquidity', 0))
                            return self.format_result(token_pair, price, liquidity_usd)
                            
            # If API fails, fall back to on-chain data
            # This would require contract interactions to get reserves and calculate price
            # For simplicity, we'll just return None in this example
            logger.warning(f"Failed to get {token_pair} price from PancakeSwap API")
            return None
            
        except Exception as e:
            logger.error(f"Error getting price from PancakeSwap: {str(e)}")
            return None
            
    async def get_liquidity(self, token_pair: str) -> Optional[float]:
        """
        Get liquidity data for a token pair from PancakeSwap
        
        Args:
            token_pair: Token pair (e.g., "ETH-USDT")
            
        Returns:
            Liquidity in USD or None if failed
        """
        # Similar implementation to get_price, but we only need the liquidity value
        result = await self.get_price(token_pair)
        return result.get('liquidity') if result else None


class UniswapV3Interface(DEXInterface):
    """Interface for Uniswap V3 DEX"""
    
    def __init__(self, network: str, web3_instance):
        super().__init__(network, web3_instance)
        
        # Uniswap V3 specific settings
        self.min_api_interval = 0.5
        
        # Load contract addresses
        self.load_contract_addresses()
        
    def load_contract_addresses(self):
        """Load contract addresses for Uniswap V3"""
        # Router contract addresses
        if self.network == 'POLYGON':
            self.router_address = os.environ.get(
                "UNISWAP_V3_ROUTER_POLYGON", 
                "0xE592427A0AEce92De3Edee1F18E0157C05861564"
            )
            self.quoter_address = os.environ.get(
                "UNISWAP_V3_QUOTER_POLYGON",
                "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6"
            )
        else:
            # Uniswap V3 isn't on BSC, but we'll set placeholders
            self.router_address = None
            self.quoter_address = None
            
        # Factory contract addresses
        if self.network == 'POLYGON':
            self.factory_address = os.environ.get(
                "UNISWAP_V3_FACTORY_POLYGON",
                "0x1F98431c8aD98523631AE4a59f267346ea31F984"
            )
        else:
            self.factory_address = None
            
    async def get_price(self, token_pair: str) -> Optional[Dict]:
        """
        Get price data for a token pair from Uniswap V3
        
        Args:
            token_pair: Token pair (e.g., "ETH-USDT")
            
        Returns:
            Price data dictionary or None if failed
        """
        if self.network != 'POLYGON':
            logger.warning("Uniswap V3 interface is only implemented for Polygon network")
            return None
            
        try:
            # Parse token pair
            tokens = token_pair.split('-')
            if len(tokens) != 2:
                logger.warning(f"Invalid token pair format: {token_pair}")
                return None
                
            token_a, token_b = tokens
            
            # Uniswap V3 has a Graph API that we can use
            # For this example, we'll use a simplified approach with The Graph API
            async with aiohttp.ClientSession() as session:
                graphql_url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"
                
                # Get token addresses
                token_addresses = json.loads(os.environ.get("TOKEN_ADDRESSES", "{}"))
                token_a_address = token_addresses.get(f"{token_a}_POLYGON")
                token_b_address = token_addresses.get(f"{token_b}_POLYGON")
                
                if not token_a_address or not token_b_address:
                    logger.warning(f"Token addresses not found for {token_pair} on POLYGON")
                    return None
                    
                # GraphQL query for pool data
                query = {
                    "query": f"""
                    {{
                      pools(where: {{
                        token0: "{token_a_address.lower()}", 
                        token1: "{token_b_address.lower()}"
                      }}, orderBy: liquidity, orderDirection: desc, first: 1) {{
                        id
                        token0Price
                        token1Price
                        liquidity
                        totalValueLockedUSD
                      }}
                    }}
                    """
                }
                
                async with session.post(graphql_url, json=query) as response:
                    if response.status == 200:
                        data = await response.json()
                        pools = data.get('data', {}).get('pools', [])
                        
                        if pools and len(pools) > 0:
                            pool = pools[0]
                            price = float(pool['token0Price'])
                            liquidity_usd = float(pool['totalValueLockedUSD'])
                            return self.format_result(token_pair, price, liquidity_usd)
                            
            logger.warning(f"Failed to get {token_pair} price from Uniswap V3 GraphQL API")
            return None
            
        except Exception as e:
            logger.error(f"Error getting price from Uniswap V3: {str(e)}")
            return None
            
    async def get_liquidity(self, token_pair: str) -> Optional[float]:
        """
        Get liquidity data for a token pair from Uniswap V3
        
        Args:
            token_pair: Token pair (e.g., "ETH-USDT")
            
        Returns:
            Liquidity in USD or None if failed
        """
        result = await self.get_price(token_pair)
        return result.get('liquidity') if result else None


# Factory function to create DEX interfaces
def create_dex_interface(dex_name: str, network: str, web3_instance) -> DEXInterface:
    """
    Create a DEX interface instance based on DEX name
    
    Args:
        dex_name: DEX name
        network: Network name (BSC or POLYGON)
        web3_instance: Web3 instance for the network
        
    Returns:
        DEX interface instance
    """
    dex_name = dex_name.upper()
    
    if dex_name == 'PANCAKESWAP':
        return PancakeSwapInterface(network, web3_instance)
    elif dex_name == 'UNISWAP' or dex_name == 'UNISWAP_V3':
        return UniswapV3Interface(network, web3_instance)
    # Additional DEX interfaces would be implemented here
    # elif dex_name == 'SUSHISWAP':
    #     return SushiSwapInterface(network, web3_instance)
    # elif dex_name == 'QUICKSWAP':
    #     return QuickSwapInterface(network, web3_instance)
    # etc.
    else:
        logger.warning(f"Unsupported DEX: {dex_name}. Using a generic interface.")
        return DEXInterface(network, web3_instance)
