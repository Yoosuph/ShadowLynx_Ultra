import os
import logging
from api.app import app
from utils.config import load_config
from utils.logger import setup_logger
import asyncio
import threading
import models
from api.app import db

# Define imports that we'll use lazily to avoid immediate loading
ai_imports = {
    'FlashLoanOrchestrator': 'core.flash_loan.FlashLoanOrchestrator',
    'PriceAggregator': 'dexs.price_aggregator.PriceAggregator',
    'PredictionEngine': 'ai.prediction_engine.PredictionEngine',
    'ExecutionEngine': 'core.execution_engine.ExecutionEngine',
    'ReinvestmentModule': 'core.reinvestment.ReinvestmentModule',
    'NotificationService': 'utils.notification.NotificationService'
}

# Configure logging
setup_logger()
logger = logging.getLogger(__name__)

def initialize_database():
    """Initialize the database with required tables"""
    with app.app_context():
        db.create_all()
        logger.info("Database initialized successfully")

def start_backend_services():
    """Start all backend services needed for arbitrage"""
    try:
        # Load configuration
        config = load_config()
        
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
            
            # Initialize services
            notification_service = NotificationService(
                telegram_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
                telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID"),
                discord_webhook=os.environ.get("DISCORD_WEBHOOK")
            )
            
            price_aggregator = PriceAggregator(
                web3_bsc=config['web3_bsc'],
                web3_polygon=config['web3_polygon'],
                dex_list=config['dex_list']
            )
            
            prediction_engine = PredictionEngine(
                model_path=config.get('ai_model_path'),
                config=config
            )
            
            execution_engine = ExecutionEngine(
                web3_bsc=config['web3_bsc'],
                web3_polygon=config['web3_polygon'],
                flash_loan_contracts=config['flash_loan_contracts'],
                notification_service=notification_service
            )
            
            reinvestment_module = ReinvestmentModule(
                execution_engine=execution_engine,
                config=config
            )
            
            flash_loan_orchestrator = FlashLoanOrchestrator(
                price_aggregator=price_aggregator,
                prediction_engine=prediction_engine,
                execution_engine=execution_engine,
                reinvestment_module=reinvestment_module,
                notification_service=notification_service,
                config=config
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
