import os
import sys

# Ensure data directory exists
DATA_DIR = os.environ.get('DATA_DIR', os.path.join(os.path.dirname(__file__), 'data'))
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize database before app is created
from app import init_db
init_db()

# Create Flask app
from app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)