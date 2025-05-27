import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Default network endpoints
DEFAULT_BSC_RPC = "https://bsc-dataseed.binance.org/"
DEFAULT_POLYGON_RPC = "https://polygon-rpc.com/"

# Network configurations
NETWORK_CONFIG = {
    "BSC": {
        "rpc_url": os.environ.get("BSC_RPC_URL", DEFAULT_BSC_RPC),
        "chain_id": 56,
        "explorer_url": "https://bscscan.com/",
        "name": "Binance Smart Chain",
        "native_token": "BNB",
        "enabled": True
    },
    "POLYGON": {
        "rpc_url": os.environ.get("POLYGON_RPC_URL", DEFAULT_POLYGON_RPC),
        "chain_id": 137,
        "explorer_url": "https://polygonscan.com/",
        "name": "Polygon",
        "native_token": "MATIC",
        "enabled": True
    }
}

# DEX configurations
DEX_CONFIG = {
    "PANCAKESWAP": {
        "networks": ["BSC"],
        "router_address_bsc": os.environ.get("PANCAKESWAP_ROUTER_BSC", "0x10ED43C718714eb63d5aA57B78B54704E256024E"),
        "factory_address_bsc": os.environ.get("PANCAKESWAP_FACTORY_BSC", "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"),
        "enabled": True,
        "fee_tier": 0.0025  # 0.25%
    },
    "UNISWAP_V3": {
        "networks": ["POLYGON"],
        "router_address_polygon": os.environ.get("UNISWAP_V3_ROUTER_POLYGON", "0xE592427A0AEce92De3Edee1F18E0157C05861564"),
        "quoter_address_polygon": os.environ.get("UNISWAP_V3_QUOTER_POLYGON", "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6"),
        "factory_address_polygon": os.environ.get("UNISWAP_V3_FACTORY_POLYGON", "0x1F98431c8aD98523631AE4a59f267346ea31F984"),
        "enabled": True,
        "fee_tier": 0.003  # 0.3%
    },
    "QUICKSWAP": {
        "networks": ["POLYGON"],
        "router_address_polygon": os.environ.get("QUICKSWAP_ROUTER_POLYGON", "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"),
        "factory_address_polygon": os.environ.get("QUICKSWAP_FACTORY_POLYGON", "0x5757371414417b8C6CAad45bAeF941aBc7d3Ab32"),
        "enabled": True,
        "fee_tier": 0.003  # 0.3%
    },
    "SUSHISWAP": {
        "networks": ["BSC", "POLYGON"],
        "router_address_bsc": os.environ.get("SUSHISWAP_ROUTER_BSC", "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506"),
        "factory_address_bsc": os.environ.get("SUSHISWAP_FACTORY_BSC", "0xc35DADB65012eC5796536bD9864eD8773aBc74C4"),
        "router_address_polygon": os.environ.get("SUSHISWAP_ROUTER_POLYGON", "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506"),
        "factory_address_polygon": os.environ.get("SUSHISWAP_FACTORY_POLYGON", "0xc35DADB65012eC5796536bD9864eD8773aBc74C4"),
        "enabled": True,
        "fee_tier": 0.003  # 0.3%
    }
}

# Flash loan provider configurations
FLASH_LOAN_CONFIG = {
    "AAVE": {
        "networks": ["POLYGON"],
        "contract_address_polygon": os.environ.get("AAVE_FLASHLOAN_POLYGON", "0x8dFf5E27EA6b7AC08EbFdf9eB090F32ee9a30fcf"),
        "fee_percentage": 0.0009,  # 0.09%
        "enabled": True
    },
    "DODO": {
        "networks": ["BSC", "POLYGON"],
        "contract_address_bsc": os.environ.get("DODO_FLASHLOAN_BSC", "0x85F9F37680f1198246B6E6A53339A4896950785b"),
        "contract_address_polygon": os.environ.get("DODO_FLASHLOAN_POLYGON", "0x88CBf433471A0CD8240D2a12354362988b4593E5"),
        "fee_percentage": 0.001,  # 0.1%
        "enabled": True
    }
}

# Token configurations for common trading pairs
DEFAULT_TOKEN_ADDRESSES = {
    "ETH_BSC": "0x2170Ed0880ac9A755fd29B2688956BD959F933F8",
    "USDT_BSC": "0x55d398326f99059fF775485246999027B3197955",
    "USDC_BSC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
    "BUSD_BSC": "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
    "WBNB_BSC": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
    
    "ETH_POLYGON": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
    "USDT_POLYGON": "0xc2132D31c914a87C6611C10748AEb04B58e8F",
    "USDC_POLYGON": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    "WMATIC_POLYGON": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"
}

# ABI (Application Binary Interface) for smart contracts
ERC20_ABI = json.loads(os.environ.get("ERC20_ABI", """[
    {"constant":true,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"type":"function"},
    {"constant":true,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},
    {"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},
    {"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},
    {"constant":true,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"type":"function"}
]"""))

# AI configuration
AI_CONFIG = {
    "model": "gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024
    "confidence_threshold": float(os.environ.get("AI_CONFIDENCE_THRESHOLD", "0.6")),
    "explanation_detail_level": os.environ.get("AI_EXPLANATION_DETAIL", "medium"),
    "request_timeout": 30,  # seconds
    "enabled": True
}

# Trading configuration
TRADING_CONFIG = {
    "min_profit_threshold_usd": float(os.environ.get("MIN_PROFIT_THRESHOLD_USD", "10.0")),
    "min_loan_amount_usd": float(os.environ.get("MIN_LOAN_AMOUNT_USD", "1000")),
    "max_loan_amount_usd": float(os.environ.get("MAX_LOAN_AMOUNT_USD", "50000")),
    "execution_interval_ms": int(os.environ.get("EXECUTION_INTERVAL_MS", "500")),
    "max_concurrent_executions": int(os.environ.get("MAX_CONCURRENT_EXECUTIONS", "3")),
    "use_flashbots": os.environ.get("USE_FLASHBOTS", "false").lower() == "true",
    "max_slippage_percent": float(os.environ.get("MAX_SLIPPAGE_PERCENT", "1.0")),
    "token_pairs": [
        "ETH-USDT",
        "ETH-USDC",
        "WBNB-BUSD",
        "WMATIC-USDC"
    ]
}

# Gateway configuration
GATEWAY_CONFIG = {
    "enabled": os.environ.get("USE_GATEWAY", "false").lower() == "true",
    "url": os.environ.get("GATEWAY_URL", "http://localhost:15888"),
    "passphrase": os.environ.get("GATEWAY_PASSPHRASE", ""),
    "dev_mode": os.environ.get("GATEWAY_DEV_MODE", "true").lower() == "true",
    "use_proxy": os.environ.get("GATEWAY_USE_PROXY", "false").lower() == "true",
    "proxy_path": os.environ.get("GATEWAY_PROXY_PATH", "/gateway"),
    "chains": {
        "BSC": {
            "enabled": True,
            "chain_name": "ethereum",  # BSC uses Ethereum chain type in Gateway
            "connectors": ["uniswap"]  # PancakeSwap uses Uniswap connector in Gateway
        },
        "POLYGON": {
            "enabled": True,
            "chain_name": "ethereum",  # Polygon uses Ethereum chain type in Gateway
            "connectors": ["uniswap"]  # QuickSwap, SushiSwap use Uniswap connector
        },
        "SOLANA": {
            "enabled": False,  # Disabled by default, enable when needed
            "chain_name": "solana",
            "connectors": ["jupiter", "raydium", "meteora"]
        }
    },
    "fallback_on_error": True  # Use direct DEX connection if Gateway fails
}

# Get token addresses from environment or use defaults
def get_token_addresses():
    """Get token addresses from environment or default values"""
    env_token_addresses = os.environ.get("TOKEN_ADDRESSES")
    if env_token_addresses:
        try:
            return json.loads(env_token_addresses)
        except json.JSONDecodeError:
            pass
    return DEFAULT_TOKEN_ADDRESSES

# Get all enabled DEXs for a specific network
def get_enabled_dexes(network):
    """Get all enabled DEXs for a specific network"""
    return [
        dex_name for dex_name, dex_config in DEX_CONFIG.items()
        if dex_config["enabled"] and network in dex_config["networks"]
    ]

# Get all enabled flash loan providers for a specific network
def get_enabled_flash_loan_providers(network):
    """Get all enabled flash loan providers for a specific network"""
    return [
        provider for provider, config in FLASH_LOAN_CONFIG.items()
        if config["enabled"] and network in config["networks"]
    ]