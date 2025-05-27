import os
import logging
from api.app import app
import asyncio
import threading
import models
from api.app import db, init_db
import config

# Define imports that we'll use lazily to avoid immediate loading
ai_imports = {
    'FlashLoanOrchestrator': 'core.flash_loan.FlashLoanOrchestrator',
    'PriceAggregator': 'dexs.price_aggregator.PriceAggregator',
    'PredictionEngine': 'ai.prediction_engine.PredictionEngine',
    'ExecutionEngine': 'core.execution_engine.ExecutionEngine',
    'ReinvestmentModule': 'core.reinvestment.ReinvestmentModule',
    'NotificationService': 'utils.notification.NotificationService',
    'AIAgent': 'ai.agent.AIAgent',
    'GatewayAdapter': 'utils.gateway_adapter.GatewayAdapter'
}

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger.info("Logger initialized with level: %s", logging.getLevelName(logger.level))

def initialize_database():
    """Initialize the database with required tables"""
    init_db()
    logger.info("Database initialized successfully")

async def start_gateway_service():
    """Initialize and start the Gateway service if enabled"""
    if config.GATEWAY_CONFIG.get("enabled", False):
        try:
            # Import GatewayAdapter dynamically
            from importlib import import_module
            module_path, class_name = ai_imports['GatewayAdapter'].rsplit('.', 1)
            GatewayAdapter = getattr(import_module(module_path), class_name)
            
            # Initialize Gateway adapter with proxy settings if enabled
            use_proxy = config.GATEWAY_CONFIG.get("use_proxy", False)
            proxy_path = config.GATEWAY_CONFIG.get("proxy_path", "/gateway") if use_proxy else ""
            
            gateway = GatewayAdapter(
                base_url=config.GATEWAY_CONFIG.get("url"),
                use_proxy=use_proxy,
                proxy_path=proxy_path
            )
            
            # Connect to Gateway
            await gateway.connect()
            
            # Check Gateway status
            status = await gateway.get_status()
            if status.get("status") == "ok":
                logger.info(f"Successfully connected to Gateway at {gateway.base_url}{proxy_path}")
                return gateway
            else:
                logger.warning(f"Gateway connection issue: {status.get('message', 'Unknown error')}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to start Gateway service: {str(e)}")
            return None
    else:
        logger.info("Gateway integration is disabled in configuration")
        return None

async def start_backend_services():
    """Start all backend services needed for arbitrage"""
    try:
        # Import modules lazily
        try:
            # Import dynamically to avoid immediate loading
            from importlib import import_module
            
            module_path, class_name = ai_imports['NotificationService'].rsplit('.', 1)
            NotificationService = getattr(import_module(module_path), class_name)
            
            module_path, class_name = ai_imports['PriceAggregator'].rsplit('.', 1)
            PriceAggregator = getattr(import_module(module_path), class_name)
            
            module_path, class_name = ai_imports['PredictionEngine'].rsplit('.', 1)
            PredictionEngine = getattr(import_module(module_path), class_name)
            
            module_path, class_name = ai_imports['ExecutionEngine'].rsplit('.', 1)
            ExecutionEngine = getattr(import_module(module_path), class_name)
            
            module_path, class_name = ai_imports['ReinvestmentModule'].rsplit('.', 1)
            ReinvestmentModule = getattr(import_module(module_path), class_name)
            
            module_path, class_name = ai_imports['FlashLoanOrchestrator'].rsplit('.', 1)
            FlashLoanOrchestrator = getattr(import_module(module_path), class_name)
            
            module_path, class_name = ai_imports['AIAgent'].rsplit('.', 1)
            AIAgent = getattr(import_module(module_path), class_name)
            
            # Initialize Gateway service
            gateway = await start_gateway_service()
            
            # Initialize AI agent
            ai_agent = AIAgent(api_key=os.environ.get("OPENAI_API_KEY"))
            
            # Initialize notification service
            notification_service = NotificationService(
                telegram_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
                telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID"),
                discord_webhook=os.environ.get("DISCORD_WEBHOOK")
            )
            
            # Initialize price aggregator (using singleton dex_manager)
            price_aggregator = PriceAggregator()
            
            # Initialize prediction engine
            prediction_engine = PredictionEngine(
                model_path=None,  # Auto-detect the best model
                config=config.AI_CONFIG
            )
            
            # Initialize execution engine with Gateway support
            execution_engine = ExecutionEngine(
                private_key=os.environ.get("WALLET_PRIVATE_KEY"),
                notification_service=notification_service,
                use_flashbots=config.TRADING_CONFIG["use_flashbots"]
            )
            
            # Initialize execution engine's async components
            await execution_engine.initialize()
            
            # Initialize reinvestment module
            reinvestment_module = ReinvestmentModule(
                execution_engine=execution_engine,
                config=config.TRADING_CONFIG
            )
            
            # Initialize flash loan orchestrator
            flash_loan_orchestrator = FlashLoanOrchestrator(
                price_aggregator=price_aggregator,
                prediction_engine=prediction_engine,
                execution_engine=execution_engine,
                reinvestment_module=reinvestment_module,
                notification_service=notification_service,
                config=config.TRADING_CONFIG
            )
            
            # Start services in separate threads/processes
            await flash_loan_orchestrator.start_monitoring()
            
        except Exception as e:
            logger.error(f"Error initializing AI components: {str(e)}")
            # Continue without AI components
        
    except Exception as e:
        logger.error(f"Failed to start backend services: {str(e)}")
        # We'll proceed with just the web interface in this case

def start_api_server():
    """Start the API server"""
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logger.error(f"Failed to start API server: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        # Initialize database
        initialize_database()
        
        # Start backend in a separate thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Create a task for the backend services
        backend_task = loop.create_task(start_backend_services())
        
        # Run the event loop in a separate thread
        def run_async_loop():
            loop.run_forever()
            
        backend_thread = threading.Thread(target=run_async_loop)
        backend_thread.daemon = True
        backend_thread.start()
        
        # Start API server in main thread
        start_api_server()
        
    except Exception as e:
        logger.critical(f"Application failed to start: {str(e)}")