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
    'AIAgent': 'ai.agent.AIAgent'
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

def start_backend_services():
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
            
            # Initialize execution engine
            execution_engine = ExecutionEngine(
                private_key=os.environ.get("TRADING_PRIVATE_KEY"),
                notification_service=notification_service,
                use_flashbots=config.TRADING_CONFIG["use_flashbots"]
            )
            
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
            asyncio.run(flash_loan_orchestrator.start_monitoring())
            
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
        backend_thread = threading.Thread(target=start_backend_services)
        backend_thread.daemon = True
        backend_thread.start()
        
        # Start API server in main thread
        start_api_server()
        
    except Exception as e:
        logger.critical(f"Application failed to start: {str(e)}")
