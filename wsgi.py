import os
import sys

# Ensure data directory exists
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('DATA_DIR', os.path.join(BASE_DIR, 'data'))
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize database before app is created
from app import init_db
init_db()

# Create Flask app
from app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)