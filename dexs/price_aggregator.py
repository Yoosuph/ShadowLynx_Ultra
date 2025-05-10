import logging
import asyncio
import time
import aiohttp
from typing import Dict, List, Optional, Any
import os
import json
from web3 import Web3
from models import TokenPrice, db
from datetime import datetime

logger = logging.getLogger(__name__)

class PriceAggregator:
    """
    Aggregates and normalizes real-time token prices from multiple DEXs
    on BSC and Polygon networks
    """
    
    def __init__(self, web3_bsc, web3_polygon, dex_list):
        """
        Initialize the PriceAggregator
        
        Args:
            web3_bsc: Web3 instance for BSC
            web3_polygon: Web3 instance for Polygon
            dex_list: List of DEXs to monitor
        """
        self.web3_bsc = web3_bsc
        self.web3_polygon = web3_polygon
        self.dex_list = dex_list
        
        # Initialize token list
        self.token_list = json.loads(os.environ.get("MONITORED_TOKENS", "[]"))
        
        # Initialize DEX interface mapping
        self.initialize_dex_interfaces()
        
        # Cached price data
        self.price_cache = {}
        self.last_update = 0
        self.update_interval = int(os.environ.get("PRICE_UPDATE_INTERVAL_MS", "1000"))
        
        # Semaphore to limit concurrent API calls
        self.api_semaphore = asyncio.Semaphore(50)
        
        # Rate limiting settings
        self.rate_limits = {}
        
    def initialize_dex_interfaces(self):
        """Initialize DEX interface handlers"""
        # Import dex interfaces dynamically
        from dexs.dex_interfaces import create_dex_interface
        
        self.dex_interfaces = {}
        for dex_name in self.dex_list:
            try:
                # Create interface for BSC
                self.dex_interfaces[f"{dex_name}_BSC"] = create_dex_interface(
                    dex_name, 'BSC', self.web3_bsc
                )
                
                # Create interface for Polygon
                self.dex_interfaces[f"{dex_name}_POLYGON"] = create_dex_interface(
                    dex_name, 'POLYGON', self.web3_polygon
                )
                
                logger.info(f"Initialized interface for {dex_name} on BSC and Polygon")
            except Exception as e:
                logger.error(f"Failed to initialize interface for {dex_name}: {str(e)}")
                
    async def start(self):
        """Start the price aggregation process"""
        logger.info("Starting price aggregation service")
        
        try:
            while True:
                await self.update_prices()
                await asyncio.sleep(self.update_interval / 1000)  # Convert ms to seconds
        except Exception as e:
            logger.error(f"Error in price aggregation service: {str(e)}")
            raise
            
    async def update_prices(self):
        """Update price data from all DEXs"""
        # Skip if update interval hasn't elapsed
        current_time = time.time() * 1000  # Convert to ms
        if current_time - self.last_update < self.update_interval:
            return
            
        self.last_update = current_time
        
        # Create tasks for all price fetching operations
        tasks = []
        for dex_key, interface in self.dex_interfaces.items():
            dex_name, network = dex_key.split('_')
            
            for token_pair in self.token_list:
                tasks.append(self.get_price_with_retry(dex_name, network, token_pair))
                
        # Execute all tasks concurrently
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions and failed results
            valid_results = [r for r in results if not isinstance(r, Exception) and r is not None]
            
            # Update price cache
            for result in valid_results:
                cache_key = f"{result['token_pair']}_{result['dex_name']}_{result['network']}"
                self.price_cache[cache_key] = result
                
            # Save to database
            await self.save_prices_to_db(valid_results)
            
            logger.debug(f"Updated prices for {len(valid_results)} token pairs")
            
        except Exception as e:
            logger.error(f"Error updating prices: {str(e)}")
            
    async def get_price_with_retry(self, dex_name: str, network: str, token_pair: str) -> Optional[Dict]:
        """
        Get price data with retry logic
        
        Args:
            dex_name: DEX name
            network: Network name (BSC or POLYGON)
            token_pair: Token pair (e.g., "ETH-USDT")
            
        Returns:
            Price data dictionary or None if failed
        """
        max_retries = 3
        base_delay = 1.0
        
        # Apply rate limiting
        rate_limit_key = f"{dex_name}_{network}"
        if rate_limit_key in self.rate_limits:
            last_call, min_interval = self.rate_limits[rate_limit_key]
            time_since_last = time.time() - last_call
            if time_since_last < min_interval:
                await asyncio.sleep(min_interval - time_since_last)
                
        # Use semaphore to limit concurrent API calls
        async with self.api_semaphore:
            for attempt in range(max_retries):
                try:
                    # Get DEX interface
                    interface_key = f"{dex_name}_{network}"
                    interface = self.dex_interfaces.get(interface_key)
                    
                    if not interface:
                        logger.warning(f"No interface found for {interface_key}")
                        return None
                        
                    # Update rate limit tracking
                    self.rate_limits[rate_limit_key] = (time.time(), interface.min_api_interval)
                    
                    # Get price from interface
                    price_data = await interface.get_price(token_pair)
                    
                    if price_data:
                        # Add additional information
                        price_data['dex_name'] = dex_name
                        price_data['network'] = network
                        price_data['timestamp'] = time.time()
                        return price_data
                        
                except Exception as e:
                    logger.warning(f"Error fetching price from {dex_name} on {network} for {token_pair}: {str(e)}")
                    
                    if attempt < max_retries - 1:
                        # Exponential backoff
                        sleep_time = base_delay * (2 ** attempt)
                        await asyncio.sleep(sleep_time)
                        
        logger.error(f"Failed to get price from {dex_name} on {network} for {token_pair} after {max_retries} attempts")
        return None
        
    async def save_prices_to_db(self, price_data_list: List[Dict]):
        """
        Save price data to database
        
        Args:
            price_data_list: List of price data dictionaries
        """
        try:
            from api.app import app
            
            async def _save_to_db():
                with app.app_context():
                    for price_data in price_data_list:
                        try:
                            # Extract token addresses from pair
                            tokens = price_data['token_pair'].split('-')
                            if len(tokens) != 2:
                                continue
                                
                            token_a, token_b = tokens
                            
                            # Get token addresses (simplified)
                            token_addresses = json.loads(os.environ.get("TOKEN_ADDRESSES", "{}"))
                            token_address = token_addresses.get(f"{token_a}_{price_data['network']}")
                            
                            if not token_address:
                                continue
                                
                            # Create or update price record
                            price_record = TokenPrice(
                                token_address=token_address,
                                token_symbol=token_a,
                                dex_name=price_data['dex_name'],
                                price_usd=price_data['price'],
                                network=price_data['network'],
                                liquidity_usd=price_data.get('liquidity'),
                                timestamp=datetime.fromtimestamp(price_data['timestamp'])
                            )
                            
                            db.session.add(price_record)
                        except Exception as e:
                            logger.error(f"Error adding price record: {str(e)}")
                    
                    # Commit all changes after processing all records
                    try:
                        db.session.commit()
                    except Exception as e:
                        logger.error(f"Error committing price records: {str(e)}")
                        db.session.rollback()
            
            # Run database operation in a separate thread to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _save_to_db)
            
        except Exception as e:
            logger.error(f"Error saving prices to database: {str(e)}")
            
    async def get_latest_prices(self) -> List[Dict]:
        """
        Get latest price data for all tokens and DEXs
        
        Returns:
            List of normalized price data dictionaries
        """
        # Return cached data if recent enough
        current_time = time.time() * 1000  # Convert to ms
        if current_time - self.last_update < self.update_interval * 2:
            return list(self.price_cache.values())
            
        # Otherwise, trigger an update and then return
        await self.update_prices()
        return list(self.price_cache.values())
        
    async def get_price_for_token_pair(self, token_pair: str, dex_name: str = None, 
                                       network: str = None) -> List[Dict]:
        """
        Get price data for a specific token pair
        
        Args:
            token_pair: Token pair (e.g., "ETH-USDT")
            dex_name: Optional DEX name filter
            network: Optional network filter
            
        Returns:
            List of price data dictionaries matching the criteria
        """
        all_prices = await self.get_latest_prices()
        
        # Filter by token pair
        results = [p for p in all_prices if p['token_pair'] == token_pair]
        
        # Apply additional filters if provided
        if dex_name:
            results = [p for p in results if p['dex_name'] == dex_name]
            
        if network:
            results = [p for p in results if p['network'] == network]
            
        return results
