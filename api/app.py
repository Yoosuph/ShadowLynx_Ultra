import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the base
db = SQLAlchemy(model_class=Base)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", os.urandom(24).hex())

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///shadowlynx.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize app with the database extension
db.init_app(app)

# Import routes after initializing db to avoid circular imports
from api import routes

# Initialize database tables
def init_db():
    with app.app_context():
        db.create_all()
        logger.info("Database tables created")

# Run server if executed directly
if __name__ == "__main__":
    # Initialize database
    init_db()
    
    # Run the Flask app
    app.run(host="0.0.0.0", port=5000, debug=True)
