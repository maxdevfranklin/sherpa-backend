from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
import os
from google.auth.transport import requests
from google.oauth2 import id_token
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from services.database import Database

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self):
        self.secret_key = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        
        # Email configuration
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.email_username = os.getenv("EMAIL_USERNAME")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        
        self.db = Database.get_instance()

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def verify_token(self, token: str):
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            user_id: str = payload.get("sub")
            if user_id is None:
                return None
            return user_id
        except jwt.JWTError:
            return None

    def authenticate_user(self, email: str, password: str):
        user = self.db.get_user_by_email(email)
        if not user:
            return False
        if not user.hashed_password:  # Google OAuth user
            return False
        if not self.db.verify_password(password, user.hashed_password):
            return False
        return user

    def register_user(self, email: str, password: str, full_name: str = None):
        # Check if user already exists
        existing_user = self.db.get_user_by_email(email)
        if existing_user:
            raise ValueError("User with this email already exists")
        
        # Create user
        user = self.db.create_user(email=email, password=password, full_name=full_name)
        
        # Send verification email
        self.send_verification_email(user.id, email)
        
        return user

    def verify_google_token(self, token: str):
        try:
            idinfo = id_token.verify_oauth2_token(token, requests.Request(), self.google_client_id)
            
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError('Wrong issuer.')
            
            google_user_id = idinfo['sub']
            email = idinfo['email']
            name = idinfo.get('name')
            
            # Check if user exists with Google ID
            user = self.db.get_user_by_google_id(google_user_id)
            if not user:
                # Check if user exists with email
                user = self.db.get_user_by_email(email)
                if user:
                    # Link Google account to existing user
                    # Update user with Google ID
                    session = self.db._Session()
                    try:
                        user.google_id = google_user_id
                        user.is_verified = True
                        if not user.full_name and name:
                            user.full_name = name
                        session.add(user)
                        session.commit()
                        session.refresh(user)
                    finally:
                        session.close()
                else:
                    # Create new user with Google account
                    user = self.db.create_user(
                        email=email,
                        full_name=name,
                        google_id=google_user_id
                    )
            
            return user
            
        except ValueError as e:
            logger.error(f"Google token verification failed: {e}")
            return None

    def send_verification_email(self, user_id: str, email: str):
        if not self.email_username or not self.email_password:
            logger.warning("Email credentials not configured, skipping email verification")
            return
        
        try:
            # Create verification code
            verification = self.db.create_verification_code(user_id)
            
            # Create email
            msg = MIMEMultipart()
            msg['From'] = self.email_username
            msg['To'] = email
            msg['Subject'] = "Verify Your Email - Fashion Guide Chat"
            
            body = f"""
            Hello!
            
            Thank you for registering with Fashion Guide Chat.
            
            Your verification code is: {verification.verification_code}
            
            This code will expire in 15 minutes.
            
            If you didn't request this, please ignore this email.
            
            Best regards,
            Fashion Guide Chat Team
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_username, self.email_password)
            text = msg.as_string()
            server.sendmail(self.email_username, email, text)
            server.quit()
            
            logger.info(f"Verification email sent to {email}")
            
        except Exception as e:
            logger.error(f"Failed to send verification email: {e}")
            raise

    def verify_email_code(self, user_id: str, code: str):
        if self.db.verify_code(user_id, code):
            self.db.update_user_verification(user_id, True)
            return True
        return False

    def resend_verification_code(self, email: str):
        user = self.db.get_user_by_email(email)
        if not user:
            raise ValueError("User not found")
        
        if user.is_verified:
            raise ValueError("Email already verified")
        
        self.send_verification_email(user.id, email)
        return True 