import os
from dotenv import load_dotenv

load_dotenv()

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///portfolio.db')

# Flask Configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-12345')
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

# AWS Configuration
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'ap-south-1')
S3_BUCKET = os.getenv('S3_BUCKET')

# Application Settings
PORT = int(os.getenv('PORT', 5000))
UPLOAD_MAX_SIZE = int(os.getenv('UPLOAD_MAX_SIZE', 16777216))  # 16MB