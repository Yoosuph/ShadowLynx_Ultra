from api.app import db
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON
import datetime

class ArbitrageOpportunity(db.Model):
    """Model for arbitrage opportunities identified by the system"""
    id = db.Column(db.Integer, primary_key=True)
    token_pair = db.Column(db.String(30), nullable=False)
    source_dex = db.Column(db.String(50), nullable=False)
    target_dex = db.Column(db.String(50), nullable=False)
    source_price = db.Column(db.Float, nullable=False)
    target_price = db.Column(db.Float, nullable=False)
    price_difference_percent = db.Column(db.Float, nullable=False)
    estimated_profit_usd = db.Column(db.Float, nullable=False)
    network = db.Column(db.String(50), nullable=False)  # BSC or Polygon
    flash_loan_provider = db.Column(db.String(50))
    loan_amount = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    ai_confidence = db.Column(db.Float)  # AI model confidence score
    is_executed = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f"<ArbitrageOpportunity {self.token_pair} {self.source_dex}->{self.target_dex} {self.price_difference_percent}%>"

class ArbitrageExecution(db.Model):
    """Model for executed arbitrage trades"""
    id = db.Column(db.Integer, primary_key=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey('arbitrage_opportunity.id'))
    transaction_hash = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # success, failed, pending
    actual_profit_usd = db.Column(db.Float)
    gas_cost_usd = db.Column(db.Float)
    net_profit_usd = db.Column(db.Float)
    executed_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    execution_time_ms = db.Column(db.Integer)  # Execution time in milliseconds
    flash_loan_fee = db.Column(db.Float)
    error_message = db.Column(db.String(255))
    
    def __repr__(self):
        return f"<ArbitrageExecution {self.transaction_hash} {self.status} ${self.net_profit_usd}>"

class TokenPrice(db.Model):
    """Model for token price data from various DEXs"""
    id = db.Column(db.Integer, primary_key=True)
    token_address = db.Column(db.String(50), nullable=False)
    token_symbol = db.Column(db.String(20))
    dex_name = db.Column(db.String(50), nullable=False)
    price_usd = db.Column(db.Float, nullable=False)
    network = db.Column(db.String(20), nullable=False)
    liquidity_usd = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<TokenPrice {self.token_symbol} on {self.dex_name}: ${self.price_usd}>"

class SystemStatus(db.Model):
    """Model for system status and health metrics"""
    id = db.Column(db.Integer, primary_key=True)
    service_name = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # online, offline, degraded
    last_check = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    uptime_seconds = db.Column(db.Integer)
    response_time_ms = db.Column(db.Integer)
    error_count = db.Column(db.Integer, default=0)
    details = db.Column(db.JSON)
    
    def __repr__(self):
        return f"<SystemStatus {self.service_name}: {self.status}>"

class ProfitSummary(db.Model):
    """Model for tracking overall profit statistics"""
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, index=True)
    total_profit_usd = db.Column(db.Float, default=0)
    total_transactions = db.Column(db.Integer, default=0)
    success_rate = db.Column(db.Float, default=0)  # Percentage of successful transactions
    avg_profit_per_trade = db.Column(db.Float, default=0)
    most_profitable_pair = db.Column(db.String(30))
    total_gas_spent = db.Column(db.Float, default=0)
    total_flash_loan_fees = db.Column(db.Float, default=0)
    
    def __repr__(self):
        return f"<ProfitSummary {self.date}: ${self.total_profit_usd}>"

class AIModelPerformance(db.Model):
    """Model for tracking AI prediction model performance"""
    id = db.Column(db.Integer, primary_key=True)
    model_version = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    accuracy = db.Column(db.Float)
    precision = db.Column(db.Float)
    recall = db.Column(db.Float)
    f1_score = db.Column(db.Float)
    mean_absolute_error = db.Column(db.Float)
    training_duration_seconds = db.Column(db.Integer)
    sample_size = db.Column(db.Integer)
    notes = db.Column(db.String(255))
    
    def __repr__(self):
        return f"<AIModelPerformance {self.model_version}: accuracy={self.accuracy}>"
