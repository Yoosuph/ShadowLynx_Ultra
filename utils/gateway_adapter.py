import os
import logging
import aiohttp
import asyncio
from typing import Dict, List, Optional, Any, Union
import json

logger = logging.getLogger(__name__)

class GatewayAdapter:
    """Adapter for Hummingbot Gateway integration"""
    
    def __init__(self, base_url: str = None, use_proxy: bool = False, proxy_path: str = "/gateway"):
        self.use_proxy = use_proxy
        self.proxy_path = proxy_path if use_proxy else ""
        self.base_url = base_url or os.environ.get("GATEWAY_URL", "http://localhost:15888")
        self.session = None
        self.initialized = False
    
    async def connect(self):
        """Initialize HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
            self.initialized = True
            logger.info(f"Connected to Gateway at {self.base_url}")
    
    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.initialized = False
            logger.info("Disconnected from Gateway")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get Gateway status"""
        await self.connect()
        try:
            async with self.session.get(f"{self.base_url}{self.proxy_path}/status") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Gateway status request failed: {error_text}")
                    return {"status": "error", "message": error_text}
        except Exception as e:
            logger.error(f"Error getting status from Gateway: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def get_price(self, chain: str, connector: str, base_token: str, quote_token: str, amount: float, side: str = "buy") -> Dict[str, Any]:
        """Get price data from Gateway"""
        await self.connect()
        try:
            endpoint = f"{self.proxy_path}/connectors/{connector}/price"
            payload = {
                "chain": chain,
                "network": "mainnet",
                "connector": connector,
                "base": base_token,
                "quote": quote_token,
                "amount": str(amount),
                "side": side
            }
            
            async with self.session.post(f"{self.base_url}{endpoint}", json=payload) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Gateway price request failed: {error_text}")
                    return {"error": error_text}
        except Exception as e:
            logger.error(f"Error getting price from Gateway: {str(e)}")
            return {"error": str(e)}
    
    async def get_balances(self, chain: str, address: str) -> Dict[str, Any]:
        """Get wallet balances from Gateway"""
        await self.connect()
        try:
            endpoint = f"{self.proxy_path}/chains/{chain}/balances"
            params = {
                "chain": chain,
                "network": "mainnet",
                "address": address
            }
            
            async with self.session.get(f"{self.base_url}{endpoint}", params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Gateway balances request failed: {error_text}")
                    return {"error": error_text}
        except Exception as e:
            logger.error(f"Error getting balances from Gateway: {str(e)}")
            return {"error": str(e)}
    
    async def execute_trade(self, chain: str, connector: str, wallet: str, base_token: str, quote_token: str, 
                           amount: float, side: str, price: float = None) -> Dict[str, Any]:
        """Execute a trade through Gateway"""
        await self.connect()
        try:
            endpoint = f"{self.proxy_path}/connectors/{connector}/trade"
            payload = {
                "chain": chain,
                "network": "mainnet",
                "connector": connector,
                "wallet": wallet,
                "base": base_token,
                "quote": quote_token,
                "amount": str(amount),
                "side": side
            }
            
            if price:
                payload["limitPrice"] = str(price)
            
            async with self.session.post(f"{self.base_url}{endpoint}", json=payload) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Gateway trade request failed: {error_text}")
                    return {"error": error_text}
        except Exception as e:
            logger.error(f"Error executing trade through Gateway: {str(e)}")
            return {"error": str(e)}
    
    # Helper methods to map BlockchainFusion parameters to Gateway parameters
    def map_network_to_chain(self, network: str) -> str:
        """Map BlockchainFusion network to Gateway chain"""
        network_map = {
            "BSC": "ethereum",  # BSC is an EVM chain, so Gateway treats it as ethereum
            "POLYGON": "ethereum",  # Polygon is an EVM chain
            "SOLANA": "solana"
        }
        return network_map.get(network.upper(), "ethereum")
    
    def map_dex_to_connector(self, dex_name: str) -> str:
        """Map BlockchainFusion DEX name to Gateway connector"""
        dex_map = {
            "PANCAKESWAP": "uniswap",  # PancakeSwap is Uniswap-like
            "UNISWAP_V3": "uniswap",
            "QUICKSWAP": "uniswap",  # QuickSwap is Uniswap-like
            "SUSHISWAP": "uniswap",  # SushiSwap is Uniswap-like
            "JUPITER": "jupiter",
            "RAYDIUM": "raydium",
            "METEORA": "meteora"
        }
        return dex_map.get(dex_name.upper(), "uniswap")
