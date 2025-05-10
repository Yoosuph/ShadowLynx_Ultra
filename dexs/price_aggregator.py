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
import config
from dexs.dex_manager import dex_manager

logger = logging.getLogger(__name__)

class PriceAggregator:
    """
    Aggregates and normalizes real-time token prices from multiple DEXs
    on BSC and Polygon networks
    """
    
    def __init__(self):
        """
        Initialize the PriceAggregator
        """
        # Initialize token list from config
        self.token_list = config.TRADING_CONFIG.get("token_pairs", [])
        
        # Cached price data
        self.price_cache = {}
        self.last_update = 0
        self.update_interval = int(os.environ.get("PRICE_UPDATE_INTERVAL_MS", "1000"))
        
        # Semaphore to limit concurrent API calls
        self.api_semaphore = asyncio.Semaphore(50)
        
        # Rate limiting settings
        self.rate_limits = {}
        
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
        
        # Get available DEXs from the DEX manager
        available_dexs = dex_manager.get_available_dexs()
        
        # Create tasks for all price fetching operations
        tasks = []
        for network, dex_names in available_dexs.items():
            for dex_name in dex_names:
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
                    # Use the DEX manager to get prices
                    price_data = await dex_manager.get_price(token_pair, dex_name, network)
                    
                    if price_data:
                        # Add additional information if not already present
                        if 'dex_name' not in price_data:
                            price_data['dex_name'] = dex_name
                        if 'network' not in price_data:
                            price_data['network'] = network
                        if 'timestamp' not in price_data:
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
        if current_time - self.last_update < self.update_interval * 2 and self.price_cache:
            return list(self.price_cache.values())
            
        # Otherwise, trigger an update and then return
        await self.update_prices()
        
        # If cache is still empty, fetch prices directly
        if not self.price_cache:
            all_prices = []
            for token_pair in self.token_list:
                try:
                    prices = await dex_manager.get_all_prices(token_pair)
                    all_prices.extend(prices)
                except Exception as e:
                    logger.error(f"Error fetching prices for {token_pair}: {str(e)}")
            return all_prices
            
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
        # If we have specific filters, try to get the data directly
        if dex_name and network:
            try:
                result = await dex_manager.get_price(token_pair, dex_name, network)
                if result:
                    # Ensure timestamp is present
                    if 'timestamp' not in result:
                        result['timestamp'] = time.time()
                    return [result]
            except Exception as e:
                logger.warning(f"Error getting direct price for {token_pair} on {dex_name} ({network}): {str(e)}")
                # Fall back to cached data
        
        # Otherwise, get all prices and filter
        if dex_name or network or not self.price_cache:
            try:
                if network and not dex_name:
                    # Get all prices for this token pair on the specified network
                    all_prices = []
                    for dex in config.get_enabled_dexes(network):
                        price = await dex_manager.get_price(token_pair, dex, network)
                        if price:
                            if 'timestamp' not in price:
                                price['timestamp'] = time.time()
                            all_prices.append(price)
                    return all_prices
                else:
                    # Use cached data with filtering
                    all_prices = await self.get_latest_prices()
                    
                    # Filter by token pair
                    results = [p for p in all_prices if p['token_pair'] == token_pair]
                    
                    # Apply additional filters if provided
                    if dex_name:
                        results = [p for p in results if p['dex_name'] == dex_name]
                        
                    if network:
                        results = [p for p in results if p['network'] == network]
                        
                    return results
            except Exception as e:
                logger.error(f"Error getting price for {token_pair}: {str(e)}")
                return []
        else:
            # Use cached data for all prices
            all_prices = list(self.price_cache.values())
            return [p for p in all_prices if p['token_pair'] == token_pair]
