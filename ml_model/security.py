import os
import jwt
from cryptography.fernet import Fernet
from datetime import datetime, timedelta
from typing import Dict, Optional

class SecurityManager:
    def __init__(self):
        self.jwt_secret = os.getenv('JWT_SECRET')
        self.encryption_key = os.getenv('ENCRYPTION_KEY')
        self.allowed_domains = os.getenv('ALLOWED_DOMAINS', '[]')
        self.fernet = Fernet(self.encryption_key.encode())

    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data before storage"""
        return self.fernet.encrypt(data.encode()).decode()

    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data for use"""
        return self.fernet.decrypt(encrypted_data.encode()).decode()

    def generate_access_token(self, user_id: str, role: str) -> str:
        """Generate JWT token for API access"""
        payload = {
            'user_id': user_id,
            'role': role,
            'exp': datetime.utcnow() + timedelta(days=1)
        }
        return jwt.encode(payload, self.jwt_secret, algorithm='HS256')

    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify JWT token and return payload if valid"""
        try:
            return jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
        except jwt.InvalidTokenError:
            return None

    def is_domain_allowed(self, email: str) -> bool:
        """Check if user's email domain is in allowed list"""
        if not email or '@' not in email:
            return False
        domain = email.split('@')[1]
        return domain in self.allowed_domains

class DataProtection:
    @staticmethod
    def sanitize_training_data(data: Dict) -> Dict:
        """Remove sensitive information from training data"""
        sensitive_fields = ['employee_ids', 'batch_numbers', 'proprietary_codes']
        sanitized = data.copy()
        
        for field in sensitive_fields:
            if field in sanitized:
                sanitized[field] = '[REDACTED]'
        
        return sanitized

    @staticmethod
    def audit_log(action: str, user_id: str, data_type: str):
        """Log all data access and modifications"""
        timestamp = datetime.now().isoformat()
        log_entry = f"{timestamp} - User {user_id} performed {action} on {data_type}"
        
        with open('audit.log', 'a') as f:
            f.write(log_entry + '\n')
