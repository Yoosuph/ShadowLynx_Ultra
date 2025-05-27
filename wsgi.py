import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set the environment
env = os.environ.get('FLASK_ENV', 'production')

# Import the Flask application
from api.app import app as application

# This allows running the application with Gunicorn
if __name__ == "__main__":
    application.run()
