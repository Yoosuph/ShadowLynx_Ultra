import logging
import time
from typing import Dict, List, Optional
import os
import json

logger = logging.getLogger(__name__)

class ReinvestmentModule:
    """
    Manages capital allocation and reinvestment of profits
    for scaling the arbitrage operations
    """
    
    def __init__(self, execution_engine, config):
        """
        Initialize the ReinvestmentModule
        
        Args:
            execution_engine: Execution engine for transactions
            config: Configuration parameters
        """
        self.execution_engine = execution_engine
        self.config = config
        
        # Initialize capital tracking
        self.initial_capital = float(os.environ.get("INITIAL_CAPITAL_USD", "1000.0"))
        self.current_capital = self.initial_capital
        self.total_profit = 0.0
        self.profit_history = []
        
        # Load allocation settings
        self.max_allocation_percent = float(os.environ.get("MAX_ALLOCATION_PERCENT", "80.0"))
        self.min_reserve_percent = float(os.environ.get("MIN_RESERVE_PERCENT", "20.0"))
        self.max_pool_impact_percent = float(os.environ.get("MAX_POOL_IMPACT_PERCENT", "2.0"))
        
        # Risk management settings
        self.max_allocation_per_trade = float(os.environ.get("MAX_ALLOCATION_PER_TRADE", "25.0"))
        self.allocation_increase_threshold = float(os.environ.get("ALLOCATION_INCREASE_THRESHOLD", "5.0"))
        
        # Load state from storage if available
        self.load_state()
        
    def load_state(self):
        """Load state from storage if available"""
        try:
            state_file = os.environ.get("STATE_FILE", "reinvestment_state.json")
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    
                    self.current_capital = state.get('current_capital', self.initial_capital)
                    self.total_profit = state.get('total_profit', 0.0)
                    self.profit_history = state.get('profit_history', [])
                    
                    logger.info(f"Loaded reinvestment state: Capital=${self.current_capital}, "
                               f"Total Profit=${self.total_profit}")
        except Exception as e:
            logger.error(f"Error loading reinvestment state: {str(e)}")
            
    def save_state(self):
        """Save current state to storage"""
        try:
            state_file = os.environ.get("STATE_FILE", "reinvestment_state.json")
            state = {
                'current_capital': self.current_capital,
                'total_profit': self.total_profit,
                'profit_history': self.profit_history,
                'last_updated': time.time()
            }
            
            with open(state_file, 'w') as f:
                json.dump(state, f)
                
            logger.debug("Saved reinvestment state")
        except Exception as e:
            logger.error(f"Error saving reinvestment state: {str(e)}")
            
    def update_capital(self, profit_amount: float):
        """
        Update capital with new profit
        
        Args:
            profit_amount: Amount of profit in USD
        """
        if profit_amount <= 0:
            return
            
        # Record the profit
        self.total_profit += profit_amount
        self.current_capital += profit_amount
        
        # Record profit in history
        self.profit_history.append({
            'amount': profit_amount,
            'timestamp': time.time()
        })
        
        # Trim history if it gets too large
        if len(self.profit_history) > 1000:
            self.profit_history = self.profit_history[-1000:]
            
        logger.info(f"Capital updated: +${profit_amount:.2f}, Total: ${self.current_capital:.2f}")
        
        # Save the updated state
        self.save_state()
        
        # Adjust allocations if needed
        self.adjust_allocations()
        
    def adjust_allocations(self):
        """Adjust capital allocations based on current performance"""
        # Calculate recent performance
        recent_profits = sum(entry['amount'] for entry in self.profit_history[-50:])
        roi_percent = (recent_profits / max(1.0, self.current_capital - recent_profits)) * 100
        
        logger.info(f"Recent performance: ${recent_profits:.2f}, ROI: {roi_percent:.2f}%")
        
        # Determine if we should increase allocation
        if roi_percent > self.allocation_increase_threshold:
            # Increase allocation percentage for next trades
            self.max_allocation_per_trade = min(
                50.0,  # Hard cap at 50%
                self.max_allocation_per_trade * (1 + (roi_percent / 100))
            )
            
            logger.info(f"Increased max allocation per trade to {self.max_allocation_per_trade:.2f}%")
        elif roi_percent < 0:
            # Poor performance, reduce allocation
            self.max_allocation_per_trade = max(
                5.0,  # Floor at 5%
                self.max_allocation_per_trade * 0.8
            )
            
            logger.info(f"Decreased max allocation per trade to {self.max_allocation_per_trade:.2f}%")
            
    def get_allocation_for_opportunity(self, opportunity: Dict) -> float:
        """
        Determine appropriate allocation for a specific opportunity
        
        Args:
            opportunity: Arbitrage opportunity details
            
        Returns:
            Allocation amount in USD
        """
        # Basic allocation based on percentage of capital
        base_allocation = self.current_capital * (self.max_allocation_per_trade / 100)
        
        # Respect min reserve requirement
        available_capital = self.current_capital * (1 - (self.min_reserve_percent / 100))
        base_allocation = min(base_allocation, available_capital)
        
        # Adjust based on opportunity specifics
        confidence_factor = opportunity.get('ai_confidence', 0.5)
        profit_factor = min(5.0, opportunity.get('estimated_profit_usd', 0) / 100)
        
        # Calculate final allocation with modifiers
        allocation = base_allocation * confidence_factor * (1 + (profit_factor / 10))
        
        # Apply pool impact limits
        if 'liquidity' in opportunity:
            max_by_liquidity = opportunity['liquidity'] * (self.max_pool_impact_percent / 100)
            allocation = min(allocation, max_by_liquidity)
            
        # Round to 2 decimal places
        allocation = round(allocation, 2)
        
        logger.debug(f"Calculated allocation for opportunity: ${allocation}")
        
        return allocation
        
    def get_capital_summary(self) -> Dict:
        """
        Get a summary of current capital status
        
        Returns:
            Dictionary with capital summary
        """
        # Calculate recent profit metrics
        recent_1h = sum(entry['amount'] for entry in self.profit_history 
                      if entry['timestamp'] > time.time() - 3600)
        recent_24h = sum(entry['amount'] for entry in self.profit_history 
                       if entry['timestamp'] > time.time() - 86400)
        
        # Calculate ROI
        roi_total = (self.total_profit / self.initial_capital) * 100 if self.initial_capital > 0 else 0
        roi_24h = (recent_24h / self.initial_capital) * 100 if self.initial_capital > 0 else 0
        
        return {
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'total_profit': self.total_profit,
            'profit_1h': recent_1h,
            'profit_24h': recent_24h,
            'roi_total_percent': roi_total,
            'roi_24h_percent': roi_24h,
            'allocation_per_trade_percent': self.max_allocation_per_trade,
            'max_pool_impact_percent': self.max_pool_impact_percent,
            'transaction_count': len(self.profit_history)
        }
        
    def redistribute_capital(self, networks: List[str], dexes: List[str]) -> Dict[str, float]:
        """
        Optimally redistribute capital across networks and DEXs
        
        Args:
            networks: List of networks
            dexes: List of DEXs
            
        Returns:
            Dictionary mapping network+DEX to allocation amount
        """
        # This is a simplified algorithm for capital redistribution
        # In a real system, this would be more sophisticated based on
        # historical performance, liquidity, and other factors
        
        total_nodes = len(networks) * len(dexes)
        if total_nodes == 0:
            return {}
            
        # Calculate available capital for redistribution
        available_capital = self.current_capital * (self.max_allocation_percent / 100)
        
        # Base allocation per network+DEX node
        base_allocation = available_capital / total_nodes
        
        # Create allocation map
        allocations = {}
        for network in networks:
            for dex in dexes:
                node_key = f"{network}_{dex}"
                allocations[node_key] = base_allocation
                
        return allocations
