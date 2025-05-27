}import os
import json
import logging
from typing import Dict, Any
import dotenv
from web3 import Web3

logger = logging.getLogger(__name__)

def load_config() -> Dict[str, Any]:
    """
    Load configuration from environment variables and files
    
    Returns:
        Dictionary with configuration
    """
    # Load .env file if exists
    dotenv.load_dotenv()
    
    # Initialize config
    config = {
        'networks': {
            'BSC': {
                'rpc_url': os.environ.get('BSC_RPC_URL', 'https://bsc-dataseed.binance.org/'),
                'chain_id': 56,
                'explorer_url': 'https://bscscan.com'
            },
            'POLYGON': {
                'rpc_url': os.environ.get('POLYGON_RPC_URL', 'https://polygon-rpc.com'),
                'chain_id': 137,
                'explorer_url': 'https://polygonscan.com'
            }
        },
        'dex_list': json.loads(os.environ.get('DEX_LIST', '["PANCAKESWAP", "UNISWAP", "SUSHISWAP", "QUICKSWAP", "APESWAP", "1INCH", "DODO", "CURVE", "BALANCER", "KYBERSWAP"]')),
        'token_list': json.loads(os.environ.get('TOKEN_LIST', '["ETH-USDT", "ETH-USDC", "BNB-BUSD", "BTC-USDT", "MATIC-USDC"]')),
        'flash_loan_providers': json.loads(os.environ.get('FLASH_LOAN_PROVIDERS', '["AAVE", "DYDX", "DODO", "UNISWAP_V3"]')),
        'preferred_flash_loan_provider': os.environ.get('PREFERRED_FLASH_LOAN_PROVIDER', 'AAVE'),
        'minimum_profit_threshold_usd': float(os.environ.get('MINIMUM_PROFIT_THRESHOLD_USD', '10.0')),
        'api_port': int(os.environ.get('API_PORT', '5000')),
        'logging_level': os.environ.get('LOGGING_LEVEL', 'INFO'),
        'use_flashbots': os.environ.get('USE_FLASHBOTS', 'true').lower() == 'true',
        'wallet_address': os.environ.get('WALLET_ADDRESS'),
        'db_url': os.environ.get('DATABASE_URL', 'sqlite:///arbitrage.db')
    }
    
    # Initialize Web3 instances
    try:
        config['web3_bsc'] = Web3(Web3.HTTPProvider(config['networks']['BSC']['rpc_url']))
        logger.info(f"Connected to BSC: {config['web3_bsc'].is_connected()}")
    except Exception as e:
        logger.error(f"Failed to connect to BSC: {str(e)}")
        config['web3_bsc'] = None
        
    try:
        config['web3_polygon'] = Web3(Web3.HTTPProvider(config['networks']['POLYGON']['rpc_url']))
        logger.info(f"Connected to Polygon: {config['web3_polygon'].is_connected()}")
    except Exception as e:
        logger.error(f"Failed to connect to Polygon: {str(e)}")
        config['web3_polygon'] = None
        
    # Load flash loan contract addresses
    contract_addresses = json.loads(os.environ.get('FLASH_LOAN_CONTRACT_ADDRESSES', '{}'))
    config['flash_loan_contracts'] = {
        'BSC': contract_addresses.get('BSC'),
        'POLYGON': contract_addresses.get('POLYGON')
    }
    
    # Load API keys
    config['api_keys'] = {
        'etherscan': os.environ.get('ETHERSCAN_API_KEY'),
        'bscscan': os.environ.get('BSCSCAN_API_KEY'),
        'polygonscan': os.environ.get('POLYGONSCAN_API_KEY')
    }
    
    # Load AI model path if exists
    ai_model_path = os.environ.get('AI_MODEL_PATH')
    if ai_model_path and os.path.exists(ai_model_path):
        config['ai_model_path'] = ai_model_path
        
    return config
    
# Gateway configuration
GATEWAY_CONFIG = {
    "enabled": os.environ.get("USE_GATEWAY", "false").lower() == "true",
    "url": os.environ.get("GATEWAY_URL", "http://localhost:15888"),
    "passphrase": os.environ.get("GATEWAY_PASSPHRASE", ""),
    "dev_mode": os.environ.get("GATEWAY_DEV_MODE", "true").lower() == "true",
    "use_proxy": os.environ.get("GATEWAY_USE_PROXY", "false").lower() == "true",
    "proxy_path": os.environ.get("GATEWAY_PROXY_PATH", "/gateway"),
    "chains": {
        # ... existing chains configuration
    }