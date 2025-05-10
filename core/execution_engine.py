import logging
import asyncio
import time
from typing import Dict, List, Optional, Any
import os
from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
from eth_account import Account
from hexbytes import HexBytes

logger = logging.getLogger(__name__)

class ExecutionEngine:
    """
    Handles the actual execution of flash loan arbitrage transactions on blockchain
    """
    
    def __init__(self, web3_bsc, web3_polygon, flash_loan_contracts, notification_service):
        """
        Initialize the ExecutionEngine
        
        Args:
            web3_bsc: Web3 instance for BSC
            web3_polygon: Web3 instance for Polygon
            flash_loan_contracts: Dictionary mapping network to flash loan contract addresses
            notification_service: Service for sending alerts
        """
        self.web3_bsc = web3_bsc
        self.web3_polygon = web3_polygon
        self.flash_loan_contracts = flash_loan_contracts
        self.notification_service = notification_service
        
        # Add POA middleware for BSC and Polygon
        self.web3_bsc.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.web3_polygon.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        self.private_key = os.environ.get("WALLET_PRIVATE_KEY")
        if not self.private_key or not self.private_key.startswith("0x"):
            self.private_key = "0x" + self.private_key if self.private_key else None
            
        # Initialize contract ABIs
        self.load_contract_abis()
        
        # Setup Flashbots integration
        self.setup_flashbots()
        
        # Mempool monitoring status
        self.mempool_monitoring = False
        
    def load_contract_abis(self):
        """Load contract ABIs from JSON files or environment variables"""
        try:
            # Flash loan contracts ABI
            self.flash_loan_abi = json.loads(os.environ.get("FLASH_LOAN_CONTRACT_ABI", "[]"))
            
            # Token ABIs
            self.erc20_abi = json.loads(os.environ.get("ERC20_ABI", "[]"))
            
            # If ABIs are empty, use default minimal ABIs
            if not self.flash_loan_abi:
                self.flash_loan_abi = [
                    {
                        "inputs": [
                            {"name": "tokenA", "type": "address"},
                            {"name": "tokenB", "type": "address"},
                            {"name": "amount", "type": "uint256"},
                            {"name": "sourceDex", "type": "string"},
                            {"name": "targetDex", "type": "string"}
                        ],
                        "name": "executeFlashloan",
                        "outputs": [{"name": "", "type": "bool"}],
                        "stateMutability": "nonpayable",
                        "type": "function"
                    }
                ]
                
            if not self.erc20_abi:
                self.erc20_abi = [
                    {
                        "constant": true,
                        "inputs": [],
                        "name": "decimals",
                        "outputs": [{"name": "", "type": "uint8"}],
                        "type": "function"
                    },
                    {
                        "constant": true,
                        "inputs": [{"name": "_owner", "type": "address"}],
                        "name": "balanceOf",
                        "outputs": [{"name": "balance", "type": "uint256"}],
                        "type": "function"
                    }
                ]
        except Exception as e:
            logger.error(f"Error loading contract ABIs: {str(e)}")
            raise
            
    def setup_flashbots(self):
        """Setup Flashbots integration for MEV protection"""
        try:
            self.use_flashbots = os.environ.get("USE_FLASHBOTS", "true").lower() == "true"
            self.flashbots_relay_bsc = os.environ.get(
                "FLASHBOTS_RELAY_BSC", 
                "https://bsc-flashbots-relay.ethermine.org"
            )
            self.flashbots_relay_polygon = os.environ.get(
                "FLASHBOTS_RELAY_POLYGON",
                "https://polygon-flashbots-relay.ethermine.org"
            )
            
            logger.info(f"Flashbots integration {'enabled' if self.use_flashbots else 'disabled'}")
        except Exception as e:
            logger.error(f"Error setting up Flashbots: {str(e)}")
            self.use_flashbots = False
            
    async def start_mempool_monitoring(self):
        """Start monitoring the mempool for large pending transactions"""
        if self.mempool_monitoring:
            return
            
        self.mempool_monitoring = True
        logger.info("Starting mempool monitoring")
        
        try:
            # Start separate tasks for BSC and Polygon
            bsc_task = asyncio.create_task(self.monitor_mempool(self.web3_bsc, 'BSC'))
            polygon_task = asyncio.create_task(self.monitor_mempool(self.web3_polygon, 'Polygon'))
            
            await asyncio.gather(bsc_task, polygon_task)
        except Exception as e:
            self.mempool_monitoring = False
            logger.error(f"Error in mempool monitoring: {str(e)}")
            await self.notification_service.send_alert(
                f"Mempool monitoring failed: {str(e)}", 
                priority="high"
            )
            
    async def monitor_mempool(self, web3_instance, network):
        """
        Monitor mempool for pending transactions on a specific network
        
        Args:
            web3_instance: Web3 instance for the network
            network: Network name (BSC or Polygon)
        """
        logger.info(f"Started mempool monitoring for {network}")
        
        # Set up a filter for pending transactions
        try:
            # Create a new filter to get pending transactions
            pending_filter = web3_instance.eth.filter('pending')
            
            while self.mempool_monitoring:
                # Get new pending transactions
                pending_tx_hashes = pending_filter.get_new_entries()
                
                # Analyze each transaction
                for tx_hash in pending_tx_hashes:
                    # Skip if too many transactions to analyze
                    if len(pending_tx_hashes) > 100:
                        logger.debug(f"Too many pending transactions ({len(pending_tx_hashes)}), skipping detailed analysis")
                        break
                    
                    try:
                        # Get transaction details
                        tx = web3_instance.eth.get_transaction(tx_hash)
                        
                        # Check if transaction is DEX-related and has significant value
                        if await self.is_significant_dex_transaction(tx, web3_instance, network):
                            await self.handle_significant_transaction(tx, network)
                    except Exception as e:
                        logger.debug(f"Error analyzing transaction {tx_hash.hex()}: {str(e)}")
                
                # Sleep to avoid overloading the node
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in {network} mempool monitoring: {str(e)}")
            self.mempool_monitoring = False
            
    async def is_significant_dex_transaction(self, tx, web3_instance, network):
        """
        Determine if a transaction is a significant DEX transaction
        
        Args:
            tx: Transaction object
            web3_instance: Web3 instance
            network: Network name
            
        Returns:
            True if the transaction is significant, False otherwise
        """
        if not tx or not tx.get('to') or not tx.get('input'):
            return False
            
        # Check transaction value
        min_tx_value = float(os.environ.get("MIN_SIGNIFICANT_TX_VALUE_ETH", "1.0"))
        tx_value_eth = web3_instance.fromWei(tx.get('value', 0), 'ether')
        
        # Known DEX contract addresses
        dex_addresses = [addr.lower() for addr in json.loads(os.environ.get("DEX_ADDRESSES", "[]"))]
        
        # Check if transaction is interacting with a DEX
        is_dex_tx = tx['to'].lower() in dex_addresses
        
        # Check function signatures for common DEX methods
        # Common function signatures for swaps (first 4 bytes of keccak hash)
        swap_signatures = [
            "0x38ed1739",  # swapExactTokensForTokens
            "0x8803dbee",  # swapTokensForExactTokens
            "0x7ff36ab5",  # swapExactETHForTokens
            "0x4a25d94a",  # swapTokensForExactETH
            "0x18cbafe5",  # swapExactTokensForETH
            "0xfb3bdb41",  # swapETHForExactTokens
            "0x5c11d795"   # swap
        ]
        
        input_data = tx.get('input', '0x')
        function_signature = input_data[:10]  # First 10 chars (including 0x)
        is_swap_tx = function_signature in swap_signatures
        
        # Check if transaction is significant
        is_significant = (is_dex_tx or is_swap_tx) and tx_value_eth >= min_tx_value
        
        if is_significant:
            logger.info(f"Detected significant DEX transaction: {tx['hash'].hex()}, "
                       f"Value: {tx_value_eth} ETH, Network: {network}")
        
        return is_significant
        
    async def handle_significant_transaction(self, tx, network):
        """
        Handle a significant DEX transaction detected in the mempool
        
        Args:
            tx: Transaction object
            network: Network name
        """
        # TODO: Implement MEV strategies (sandwiching, etc.)
        # Currently we just log and alert about significant transactions
        
        try:
            tx_hash = tx['hash'].hex()
            from_addr = tx.get('from', 'Unknown')
            to_addr = tx.get('to', 'Unknown')
            
            web3 = self.web3_bsc if network == 'BSC' else self.web3_polygon
            value_eth = web3.fromWei(tx.get('value', 0), 'ether')
            
            logger.info(f"Significant DEX transaction detected: {tx_hash}")
            logger.info(f"From: {from_addr}, To: {to_addr}")
            logger.info(f"Value: {value_eth} ETH, Network: {network}")
            
            # Alert on very large transactions
            if value_eth > float(os.environ.get("LARGE_TX_ALERT_THRESHOLD_ETH", "10.0")):
                await self.notification_service.send_alert(
                    f"Large DEX transaction detected!\n"
                    f"Hash: {tx_hash}\n"
                    f"From: {from_addr}\n"
                    f"To: {to_addr}\n"
                    f"Value: {value_eth} ETH\n"
                    f"Network: {network}",
                    priority="medium"
                )
        except Exception as e:
            logger.error(f"Error handling significant transaction: {str(e)}")
            
    async def execute_flash_loan(
        self, token_pair: str, source_dex: str, target_dex: str, amount: float, network: str
    ) -> Dict:
        """
        Execute a flash loan arbitrage transaction
        
        Args:
            token_pair: Trading pair (e.g., "ETH-USDT")
            source_dex: Source DEX name
            target_dex: Target DEX name
            amount: Loan amount in USD
            network: Network (BSC or Polygon)
            
        Returns:
            Dictionary with execution results
        """
        logger.info(f"Executing flash loan on {network} for {token_pair}: "
                   f"{source_dex} -> {target_dex}, Amount: ${amount}")
        
        try:
            # Parse token pair
            tokens = token_pair.split('-')
            if len(tokens) != 2:
                return {
                    'success': False,
                    'error': f"Invalid token pair format: {token_pair}",
                }
                
            token_a, token_b = tokens
            
            # Get token addresses from config or environment
            token_addresses = json.loads(os.environ.get("TOKEN_ADDRESSES", "{}"))
            
            # Get token addresses
            token_a_address = token_addresses.get(f"{token_a}_{network}")
            token_b_address = token_addresses.get(f"{token_b}_{network}")
            
            if not token_a_address or not token_b_address:
                return {
                    'success': False,
                    'error': f"Token addresses not found for {token_pair} on {network}",
                }
                
            # Select Web3 instance and contract
            if network.upper() == 'BSC':
                web3 = self.web3_bsc
                contract_address = self.flash_loan_contracts.get('BSC')
            elif network.upper() == 'POLYGON':
                web3 = self.web3_polygon
                contract_address = self.flash_loan_contracts.get('POLYGON')
            else:
                return {
                    'success': False,
                    'error': f"Unsupported network: {network}",
                }
                
            if not contract_address:
                return {
                    'success': False,
                    'error': f"Flash loan contract not configured for {network}",
                }
                
            # Create contract instance
            contract = web3.eth.contract(
                address=Web3.toChecksumAddress(contract_address),
                abi=self.flash_loan_abi
            )
            
            # Convert amount to wei (assuming 18 decimals)
            amount_wei = web3.toWei(amount, 'ether')
            
            # Prepare transaction
            wallet_address = Account.from_key(self.private_key).address
            
            # Estimate gas
            gas_estimate = None
            try:
                gas_estimate = contract.functions.executeFlashloan(
                    Web3.toChecksumAddress(token_a_address),
                    Web3.toChecksumAddress(token_b_address),
                    amount_wei,
                    source_dex,
                    target_dex
                ).estimateGas({'from': wallet_address})
                
                # Add 20% buffer to gas estimate
                gas_estimate = int(gas_estimate * 1.2)
            except Exception as e:
                logger.warning(f"Gas estimation failed: {str(e)}. Using default gas limit.")
                gas_estimate = 5000000  # Default gas limit
                
            # Get current gas price
            gas_price = web3.eth.gas_price
            # Add 10% to ensure quick confirmation
            gas_price = int(gas_price * 1.1)
            
            # Check if we're using Flashbots
            if self.use_flashbots:
                return await self.execute_via_flashbots(
                    web3, contract, wallet_address,
                    token_a_address, token_b_address,
                    amount_wei, source_dex, target_dex,
                    gas_estimate, gas_price, network
                )
            else:
                return await self.execute_normal_transaction(
                    web3, contract, wallet_address,
                    token_a_address, token_b_address,
                    amount_wei, source_dex, target_dex,
                    gas_estimate, gas_price
                )
                
        except Exception as e:
            logger.error(f"Error executing flash loan: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
            
    async def execute_normal_transaction(
        self, web3, contract, wallet_address,
        token_a_address, token_b_address,
        amount_wei, source_dex, target_dex,
        gas_estimate, gas_price
    ):
        """
        Execute a normal (non-Flashbots) transaction
        
        Args:
            web3: Web3 instance
            contract: Contract instance
            wallet_address: Wallet address
            token_a_address: First token address
            token_b_address: Second token address
            amount_wei: Loan amount in wei
            source_dex: Source DEX name
            target_dex: Target DEX name
            gas_estimate: Gas estimate
            gas_price: Gas price
            
        Returns:
            Dictionary with execution results
        """
        try:
            # Build transaction
            transaction = contract.functions.executeFlashloan(
                Web3.toChecksumAddress(token_a_address),
                Web3.toChecksumAddress(token_b_address),
                amount_wei,
                source_dex,
                target_dex
            ).buildTransaction({
                'from': wallet_address,
                'gas': gas_estimate,
                'gasPrice': gas_price,
                'nonce': web3.eth.get_transaction_count(wallet_address),
            })
            
            # Sign transaction
            signed_tx = web3.eth.account.sign_transaction(transaction, self.private_key)
            
            # Send transaction
            tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for transaction receipt
            receipt = None
            for i in range(30):  # Wait up to 30 * 2 seconds
                try:
                    receipt = web3.eth.get_transaction_receipt(tx_hash)
                    if receipt is not None:
                        break
                except Exception:
                    pass
                await asyncio.sleep(2)
                
            if receipt is None:
                return {
                    'success': False,
                    'error': "Transaction not confirmed after 60 seconds",
                    'tx_hash': tx_hash.hex()
                }
                
            # Check transaction status
            if receipt['status'] == 1:
                # Transaction successful
                # Parse logs to extract profit (implementation depends on contract events)
                profit_wei = self.extract_profit_from_logs(receipt)
                profit_eth = web3.fromWei(profit_wei, 'ether')
                
                # Convert ETH to USD (simplified)
                eth_price_usd = 3000  # This should come from a price feed
                profit_usd = profit_eth * eth_price_usd
                
                return {
                    'success': True,
                    'tx_hash': tx_hash.hex(),
                    'profit_wei': profit_wei,
                    'profit_eth': profit_eth,
                    'profit_usd': profit_usd,
                    'gas_used': receipt['gasUsed'],
                    'gas_cost_wei': receipt['gasUsed'] * gas_price,
                }
            else:
                return {
                    'success': False,
                    'error': "Transaction reverted",
                    'tx_hash': tx_hash.hex(),
                    'gas_used': receipt['gasUsed'],
                }
                
        except Exception as e:
            logger.error(f"Error in normal transaction execution: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
            
    async def execute_via_flashbots(
        self, web3, contract, wallet_address,
        token_a_address, token_b_address,
        amount_wei, source_dex, target_dex,
        gas_estimate, gas_price, network
    ):
        """
        Execute a transaction via Flashbots to prevent front-running
        
        Args:
            web3: Web3 instance
            contract: Contract instance
            wallet_address: Wallet address
            token_a_address: First token address
            token_b_address: Second token address
            amount_wei: Loan amount in wei
            source_dex: Source DEX name
            target_dex: Target DEX name
            gas_estimate: Gas estimate
            gas_price: Gas price
            network: Network name
            
        Returns:
            Dictionary with execution results
        """
        # This is a simplified implementation as full Flashbots integration requires
        # additional setup and dependencies
        logger.info("Executing transaction via Flashbots")
        
        try:
            # For now, fallback to regular transaction
            # In a real implementation, this would use Flashbots Provider
            return await self.execute_normal_transaction(
                web3, contract, wallet_address,
                token_a_address, token_b_address,
                amount_wei, source_dex, target_dex,
                gas_estimate, gas_price
            )
        except Exception as e:
            logger.error(f"Error in Flashbots execution: {str(e)}")
            return {
                'success': False,
                'error': f"Flashbots execution failed: {str(e)}",
            }
            
    def extract_profit_from_logs(self, receipt):
        """
        Extract profit from transaction logs
        
        Args:
            receipt: Transaction receipt
            
        Returns:
            Profit amount in wei
        """
        # This is a simplified implementation
        # In a real implementation, this would parse event logs based on contract ABI
        
        # Default to 0 profit if we can't parse logs
        profit_wei = 0
        
        # TODO: Implement log parsing based on your contract's event structure
        # Example:
        # for log in receipt['logs']:
        #     if log['topics'][0].hex() == '0xProfit_Event_Topic_Hash':
        #         profit_wei = int(log['data'], 16)
        
        return profit_wei
