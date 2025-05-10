import logging
import os
import json
from typing import Dict, List, Optional, Any
import config
from contracts.contract_interfaces import FlashLoanContract, TokenContract, FlashLoanContractFactory
from core.web3_manager import web3_manager

logger = logging.getLogger(__name__)

class ContractManager:
    """
    Manages smart contract interactions for flash loans and token operations
    """
    
    def __init__(self):
        """Initialize the ContractManager"""
        self.flash_loan_contracts = {}
        self.token_contracts = {}
        
        # Load ABIs
        self._load_abis()
        
        # Initialize contracts
        self._initialize_contracts()
        
    def _load_abis(self):
        """Load contract ABIs from environment or files"""
        # Flash loan ABIs
        self.flash_loan_abis = {}
        
        for provider, config_data in config.FLASH_LOAN_CONFIG.items():
            abi_env_var = f"{provider}_ABI"
            abi_json = os.environ.get(abi_env_var)
            
            if abi_json:
                try:
                    self.flash_loan_abis[provider] = json.loads(abi_json)
                    logger.info(f"Loaded ABI for {provider} from environment")
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in {abi_env_var}")
            else:
                # Try to load from file
                try:
                    abi_path = f"contracts/abis/{provider.lower()}_flashloan.json"
                    if os.path.exists(abi_path):
                        with open(abi_path, 'r') as f:
                            self.flash_loan_abis[provider] = json.load(f)
                        logger.info(f"Loaded ABI for {provider} from file")
                    else:
                        logger.warning(f"No ABI file found for {provider} at {abi_path}")
                except Exception as e:
                    logger.error(f"Error loading ABI file for {provider}: {str(e)}")
        
        # ERC20 ABI
        self.erc20_abi = config.ERC20_ABI
        
    def _initialize_contracts(self):
        """Initialize contract interfaces for all configured networks"""
        for network, network_config in config.NETWORK_CONFIG.items():
            if not network_config.get("enabled", False):
                continue
                
            web3_instance = web3_manager.get_web3(network)
            if not web3_instance:
                logger.warning(f"No Web3 instance for {network}, skipping contract initialization")
                continue
                
            # Initialize flash loan contracts
            for provider in config.get_enabled_flash_loan_providers(network):
                self._initialize_flash_loan_contract(provider, network, web3_instance)
                
    def _initialize_flash_loan_contract(self, provider: str, network: str, web3_instance):
        """
        Initialize a flash loan contract for a specific provider and network
        
        Args:
            provider: Flash loan provider name
            network: Network name
            web3_instance: Web3 instance
        """
        try:
            provider_config = config.FLASH_LOAN_CONFIG.get(provider, {})
            
            if network not in provider_config.get("networks", []):
                return
                
            # Get contract address
            address_key = f"contract_address_{network.lower()}"
            contract_address = provider_config.get(address_key)
            
            if not contract_address:
                logger.warning(f"No contract address for {provider} on {network}")
                return
                
            # Get ABI
            abi = self.flash_loan_abis.get(provider)
            if not abi:
                logger.warning(f"No ABI found for {provider}")
                return
                
            # Create contract interface
            contract = FlashLoanContract(contract_address, abi, web3_instance)
            
            # Store in dictionary
            key = f"{provider}_{network}"
            self.flash_loan_contracts[key] = contract
            
            logger.info(f"Initialized flash loan contract for {provider} on {network}")
            
        except Exception as e:
            logger.error(f"Error initializing flash loan contract for {provider} on {network}: {str(e)}")
            
    def get_flash_loan_contract(self, provider: str, network: str) -> Optional[FlashLoanContract]:
        """
        Get flash loan contract for a specific provider and network
        
        Args:
            provider: Flash loan provider name
            network: Network name
            
        Returns:
            Flash loan contract interface or None if not available
        """
        key = f"{provider}_{network}"
        return self.flash_loan_contracts.get(key)
        
    def get_token_contract(self, token_address: str, network: str) -> TokenContract:
        """
        Get or create token contract for a specific address and network
        
        Args:
            token_address: Token contract address
            network: Network name
            
        Returns:
            Token contract interface
        """
        key = f"{token_address}_{network}"
        
        if key in self.token_contracts:
            return self.token_contracts[key]
            
        web3_instance = web3_manager.get_web3(network)
        if not web3_instance:
            logger.warning(f"No Web3 instance for {network}, cannot create token contract")
            return None
            
        token_contract = TokenContract(token_address, web3_instance)
        self.token_contracts[key] = token_contract
        
        return token_contract
        
    def get_contract_addresses(self) -> Dict[str, Dict[str, str]]:
        """
        Get dictionary of all contract addresses
        
        Returns:
            Dictionary mapping providers and networks to contract addresses
        """
        result = {}
        
        for key, contract in self.flash_loan_contracts.items():
            provider, network = key.split('_')
            
            if provider not in result:
                result[provider] = {}
                
            result[provider][network] = contract.address
            
        return result
        
    def get_available_flash_loan_providers(self) -> Dict[str, List[str]]:
        """
        Get mapping of networks to available flash loan providers
        
        Returns:
            Dictionary mapping networks to lists of available providers
        """
        result = {}
        
        for key in self.flash_loan_contracts:
            provider, network = key.split('_')
            
            if network not in result:
                result[network] = []
                
            result[network].append(provider)
            
        return result

# Create a singleton instance
contract_manager = ContractManager()