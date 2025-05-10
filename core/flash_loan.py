import logging
import asyncio
import time
from typing import Dict, List, Optional, Tuple, Any
import os
from web3 import Web3

logger = logging.getLogger(__name__)

class FlashLoanOrchestrator:
    """
    Orchestrates the flash loan process by coordinating price aggregation,
    AI predictions, and execution across multiple DEXs
    """
    
    def __init__(self, price_aggregator, prediction_engine, execution_engine, 
                 reinvestment_module, notification_service, config):
        """
        Initialize the FlashLoanOrchestrator with necessary components
        
        Args:
            price_aggregator: Component for aggregating prices across DEXs
            prediction_engine: AI component for predicting profitable opportunities
            execution_engine: Component for executing trades
            reinvestment_module: Component for managing capital allocation
            notification_service: Service for sending alerts
            config: Configuration parameters
        """
        self.price_aggregator = price_aggregator
        self.prediction_engine = prediction_engine
        self.execution_engine = execution_engine
        self.reinvestment_module = reinvestment_module
        self.notification_service = notification_service
        self.config = config
        self.running = False
        self.minimum_profit_threshold = float(os.environ.get("MIN_PROFIT_THRESHOLD_USD", "10.0"))
        self.execution_interval = int(os.environ.get("EXECUTION_INTERVAL_MS", "500"))
        self.max_concurrent_executions = int(os.environ.get("MAX_CONCURRENT_EXECUTIONS", "3"))
        self.execution_semaphore = asyncio.Semaphore(self.max_concurrent_executions)
        
    async def start_monitoring(self):
        """Start monitoring for arbitrage opportunities"""
        self.running = True
        logger.info("Starting flash loan arbitrage monitoring")
        
        try:
            # Start price aggregator
            price_aggregation_task = asyncio.create_task(self.price_aggregator.start())
            
            # Start mempool monitoring
            mempool_monitoring_task = asyncio.create_task(self.execution_engine.start_mempool_monitoring())
            
            # Start opportunity identification and execution loop
            opportunity_task = asyncio.create_task(self.opportunity_loop())
            
            # Wait for all tasks
            await asyncio.gather(
                price_aggregation_task,
                mempool_monitoring_task,
                opportunity_task
            )
            
        except Exception as e:
            self.running = False
            logger.error(f"Error in flash loan monitoring: {str(e)}")
            await self.notification_service.send_alert(
                f"Critical error in FlashLoanOrchestrator: {str(e)}", 
                priority="high"
            )
    
    async def opportunity_loop(self):
        """Main loop that identifies and executes arbitrage opportunities"""
        while self.running:
            try:
                # Get latest price data
                price_data = await self.price_aggregator.get_latest_prices()
                
                # Identify potential arbitrage opportunities
                opportunities = self.identify_arbitrage_opportunities(price_data)
                
                # Enhance with AI predictions
                enhanced_opportunities = await self.prediction_engine.enhance_opportunities(opportunities)
                
                # Filter and sort opportunities by profitability
                viable_opportunities = self.filter_opportunities(enhanced_opportunities)
                
                # Execute top opportunities
                for opportunity in viable_opportunities[:5]:  # Limit to top 5
                    asyncio.create_task(self.execute_opportunity(opportunity))
                
                # Short sleep to prevent excessive CPU usage
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in opportunity loop: {str(e)}")
                await asyncio.sleep(5)  # Longer sleep on error
    
    def identify_arbitrage_opportunities(self, price_data: List[Dict]) -> List[Dict]:
        """
        Identify potential arbitrage opportunities from price data
        
        Args:
            price_data: List of price data dictionaries
            
        Returns:
            List of potential arbitrage opportunities
        """
        opportunities = []
        
        # Group by token pair
        token_pairs = {}
        for price_entry in price_data:
            token_pair = price_entry['token_pair']
            if token_pair not in token_pairs:
                token_pairs[token_pair] = []
            token_pairs[token_pair].append(price_entry)
        
        # Find price differences for each token pair
        for token_pair, prices in token_pairs.items():
            if len(prices) < 2:
                continue
                
            # Compare each DEX with every other DEX
            for i, source_dex in enumerate(prices):
                for target_dex in prices[i+1:]:
                    source_price = source_dex['price']
                    target_price = target_dex['price']
                    
                    # Calculate price difference percentage
                    if source_price <= 0 or target_price <= 0:
                        continue
                        
                    price_diff_pct = abs((target_price - source_price) / source_price) * 100
                    
                    # Determine direction (buy at lower, sell at higher)
                    if source_price < target_price:
                        buy_dex = source_dex
                        sell_dex = target_dex
                    else:
                        buy_dex = target_dex
                        sell_dex = source_dex
                    
                    # Estimate potential profit
                    # This is simplified - real calculation would account for fees, gas, etc.
                    estimated_profit = self.calculate_estimated_profit(
                        buy_dex, sell_dex, price_diff_pct
                    )
                    
                    # Add to opportunities if profit is positive
                    if estimated_profit > 0:
                        opportunities.append({
                            'token_pair': token_pair,
                            'buy_dex': buy_dex['dex_name'],
                            'sell_dex': sell_dex['dex_name'],
                            'buy_price': min(source_price, target_price),
                            'sell_price': max(source_price, target_price),
                            'price_diff_pct': price_diff_pct,
                            'estimated_profit_usd': estimated_profit,
                            'network': buy_dex['network'],  # Assuming both DEXs are on same network
                            'timestamp': time.time()
                        })
        
        return opportunities
    
    def calculate_estimated_profit(
        self, buy_dex: Dict, sell_dex: Dict, price_diff_pct: float
    ) -> float:
        """
        Calculate estimated profit for an arbitrage opportunity
        
        Args:
            buy_dex: DEX data for buy side
            sell_dex: DEX data for sell side
            price_diff_pct: Price difference percentage
            
        Returns:
            Estimated profit in USD
        """
        # Get loan amount based on available liquidity
        loan_amount = self.determine_loan_amount(buy_dex, sell_dex)
        
        # Calculate gross profit before fees
        gross_profit = loan_amount * (price_diff_pct / 100)
        
        # Estimate fees
        flash_loan_fee = self.estimate_flash_loan_fee(loan_amount, buy_dex['network'])
        dex_fees = self.estimate_dex_fees(loan_amount, buy_dex['dex_name'], sell_dex['dex_name'])
        gas_cost = self.estimate_gas_cost(buy_dex['network'])
        
        # Calculate net profit
        net_profit = gross_profit - flash_loan_fee - dex_fees - gas_cost
        
        return net_profit
    
    def determine_loan_amount(self, buy_dex: Dict, sell_dex: Dict) -> float:
        """
        Determine appropriate loan amount based on DEX liquidity
        
        Args:
            buy_dex: DEX data for buy side
            sell_dex: DEX data for sell side
            
        Returns:
            Appropriate loan amount in USD
        """
        # Use a percentage of the available liquidity
        # Typically, we don't want to use more than 1-2% of the pool to avoid excessive slippage
        liquidity_limit = min(
            buy_dex.get('liquidity', float('inf')),
            sell_dex.get('liquidity', float('inf'))
        ) * 0.01  # 1% of the smallest liquidity pool
        
        # Apply minimum and maximum constraints
        min_loan = float(os.environ.get("MIN_LOAN_AMOUNT_USD", "1000"))
        max_loan = float(os.environ.get("MAX_LOAN_AMOUNT_USD", "50000"))
        
        return max(min_loan, min(liquidity_limit, max_loan))
    
    def estimate_flash_loan_fee(self, loan_amount: float, network: str) -> float:
        """
        Estimate flash loan fee based on provider and amount
        
        Args:
            loan_amount: Amount to be borrowed in USD
            network: Network (BSC or Polygon)
            
        Returns:
            Estimated flash loan fee in USD
        """
        # Fee rates vary by provider:
        # - Aave: 0.09%
        # - DyDx: 0% (gas only)
        # - DODO: 0.1%
        # - Uniswap V3 Flash Swaps: ~0.05% (varies)
        
        provider = self.config.get('preferred_flash_loan_provider', 'AAVE')
        
        if provider == 'AAVE':
            return loan_amount * 0.0009
        elif provider == 'DYDX':
            return 0  # Gas only
        elif provider == 'DODO':
            return loan_amount * 0.001
        elif provider == 'UNISWAP_V3':
            return loan_amount * 0.0005
        else:
            return loan_amount * 0.001  # Default
    
    def estimate_dex_fees(self, loan_amount: float, buy_dex: str, sell_dex: str) -> float:
        """
        Estimate DEX trading fees
        
        Args:
            loan_amount: Amount to be traded in USD
            buy_dex: DEX name for buying
            sell_dex: DEX name for selling
            
        Returns:
            Estimated DEX fees in USD
        """
        # DEX fee rates (typical values)
        dex_fee_rates = {
            'PANCAKESWAP': 0.0025,  # 0.25%
            'SUSHISWAP': 0.003,     # 0.3%
            'UNISWAP': 0.003,       # 0.3%
            'QUICKSWAP': 0.003,     # 0.3%
            'APESWAP': 0.003,       # 0.3%
            '1INCH': 0.003,         # Variable, using 0.3% as estimate
            'DODO': 0.001,          # 0.1%
            'CURVE': 0.0004,        # 0.04% (varies by pool)
            'BALANCER': 0.002,      # 0.2% (varies by pool)
            'KYBERSWAP': 0.003      # 0.3%
        }
        
        # Get fee rates, default to 0.3% if DEX not found
        buy_fee_rate = dex_fee_rates.get(buy_dex.upper(), 0.003)
        sell_fee_rate = dex_fee_rates.get(sell_dex.upper(), 0.003)
        
        # Calculate total fees
        buy_fee = loan_amount * buy_fee_rate
        sell_fee = loan_amount * sell_fee_rate
        
        return buy_fee + sell_fee
    
    def estimate_gas_cost(self, network: str) -> float:
        """
        Estimate gas cost for flash loan transaction
        
        Args:
            network: Network (BSC or Polygon)
            
        Returns:
            Estimated gas cost in USD
        """
        # Gas costs vary by network and congestion
        # These are rough estimates
        if network.upper() == 'BSC':
            gas_units = 500000  # Complex flash loan on BSC
            gas_price_gwei = 5  # BSC is typically 5 Gwei
            bnb_price_usd = 300  # Estimated BNB price
            return (gas_units * gas_price_gwei * 1e-9) * bnb_price_usd
        elif network.upper() == 'POLYGON':
            gas_units = 800000  # Complex flash loan on Polygon
            gas_price_gwei = 30  # Polygon can be 30+ Gwei
            matic_price_usd = 1  # Estimated MATIC price
            return (gas_units * gas_price_gwei * 1e-9) * matic_price_usd
        else:
            return 10  # Default estimate
    
    def filter_opportunities(self, opportunities: List[Dict]) -> List[Dict]:
        """
        Filter and sort arbitrage opportunities
        
        Args:
            opportunities: List of potential arbitrage opportunities
            
        Returns:
            Filtered and sorted list of viable opportunities
        """
        # Filter by minimum profit threshold
        viable_opportunities = [
            op for op in opportunities 
            if op['estimated_profit_usd'] >= self.minimum_profit_threshold
        ]
        
        # Filter by AI confidence if available
        if viable_opportunities and 'ai_confidence' in viable_opportunities[0]:
            confidence_threshold = float(os.environ.get("AI_CONFIDENCE_THRESHOLD", "0.6"))
            viable_opportunities = [
                op for op in viable_opportunities 
                if op.get('ai_confidence', 0) >= confidence_threshold
            ]
        
        # Sort by estimated profit (descending)
        viable_opportunities.sort(
            key=lambda x: x['estimated_profit_usd'], 
            reverse=True
        )
        
        return viable_opportunities
    
    async def execute_opportunity(self, opportunity: Dict):
        """
        Execute an arbitrage opportunity using flash loans
        
        Args:
            opportunity: Arbitrage opportunity details
        """
        # Use semaphore to limit concurrent executions
        async with self.execution_semaphore:
            try:
                logger.info(f"Executing arbitrage for {opportunity['token_pair']}: "
                           f"{opportunity['buy_dex']} -> {opportunity['sell_dex']}, "
                           f"Expected profit: ${opportunity['estimated_profit_usd']:.2f}")
                
                # Determine loan amount
                loan_amount = opportunity.get('loan_amount', 
                                             self.determine_loan_amount(
                                                 {'dex_name': opportunity['buy_dex']}, 
                                                 {'dex_name': opportunity['sell_dex']}
                                             ))
                
                # Execute the flash loan
                execution_result = await self.execution_engine.execute_flash_loan(
                    token_pair=opportunity['token_pair'],
                    source_dex=opportunity['buy_dex'],
                    target_dex=opportunity['sell_dex'],
                    amount=loan_amount,
                    network=opportunity['network']
                )
                
                # Process execution result
                if execution_result['success']:
                    logger.info(f"Arbitrage executed successfully: {execution_result['tx_hash']}, "
                               f"Profit: ${execution_result['profit_usd']:.2f}")
                    
                    # Notify if profit is significant
                    if execution_result['profit_usd'] >= self.minimum_profit_threshold * 2:
                        await self.notification_service.send_alert(
                            f"Profitable arbitrage executed!\n"
                            f"Token: {opportunity['token_pair']}\n"
                            f"Route: {opportunity['buy_dex']} -> {opportunity['sell_dex']}\n"
                            f"Profit: ${execution_result['profit_usd']:.2f}\n"
                            f"Transaction: {execution_result['tx_hash']}",
                            priority="medium"
                        )
                    
                    # Update reinvestment module with new profits
                    self.reinvestment_module.update_capital(execution_result['profit_usd'])
                    
                else:
                    logger.warning(f"Arbitrage execution failed: {execution_result['error']}")
                    
                    # Notify on failure if it was a high-value opportunity
                    if opportunity['estimated_profit_usd'] >= self.minimum_profit_threshold * 5:
                        await self.notification_service.send_alert(
                            f"High-value arbitrage failed!\n"
                            f"Token: {opportunity['token_pair']}\n"
                            f"Route: {opportunity['buy_dex']} -> {opportunity['sell_dex']}\n"
                            f"Expected profit: ${opportunity['estimated_profit_usd']:.2f}\n"
                            f"Error: {execution_result['error']}",
                            priority="high"
                        )
                
                # Allow a short delay before next execution
                await asyncio.sleep(self.execution_interval / 1000)
                
            except Exception as e:
                logger.error(f"Error executing arbitrage opportunity: {str(e)}")
                await self.notification_service.send_alert(
                    f"Error executing arbitrage:\n{str(e)}",
                    priority="high"
                )
