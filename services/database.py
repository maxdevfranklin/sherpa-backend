from sqlalchemy import create_engine, Column, String, DateTime, text, Boolean, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime, timedelta
import logging
from passlib.context import CryptContext
import secrets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class History(Base):
    __tablename__ = 'history'
    
    id = Column(String, primary_key=True, server_default=text('gen_random_uuid()'))
    message_type = Column(String, nullable=False)
    content = Column(String, nullable=False)
    user_id = Column(String, nullable=True)  # Link messages to users
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))

class User(Base):
    __tablename__ = 'users'
    
    id = Column(String, primary_key=True, server_default=text('gen_random_uuid()'))
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True)  # Nullable for Google OAuth users
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    google_id = Column(String, unique=True, nullable=True)  # For Google OAuth
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'), onupdate=datetime.utcnow)

class EmailVerification(Base):
    __tablename__ = 'email_verifications'
    
    id = Column(String, primary_key=True, server_default=text('gen_random_uuid()'))
    user_id = Column(String, nullable=False)
    verification_code = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP'))

class Database:
    _instance = None
    _engine = None
    _Session = None

    def __init__(self):
        if Database._instance is not None:
            raise Exception("Database class is a singleton!")
        Database._instance = self

    @classmethod
    def get_instance(cls) -> 'Database':
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        if self._engine is None:
            # database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:SCoi~IpdVZe6x37NCP.631X9jZubPctR@centerbeam.proxy.rlwy.net:43656/railway')
            database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:WznKvjJYdMOQFPZyFMYEHccyoLKrvsTH@switchback.proxy.rlwy.net:50310/railway')
            logger.info(f"Attempting to connect to database...")
            try:
                self._engine = create_engine(database_url)
                # Test the connection
                with self._engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
                logger.info("Database connection test successful!")
                
                # Create tables
                Base.metadata.create_all(self._engine)
                logger.info("Database tables created successfully")
                
                self._Session = sessionmaker(bind=self._engine)
                logger.info("Database session factory created")
            except Exception as e:
                logger.error(f"Database connection failed: {str(e)}")
                raise

    def save_message(self, message_type: str, content: str, user_id: str = None):
        session = self._Session()
        try:
            message = History(message_type=message_type, content=content, user_id=user_id)
            session.add(message)
            session.commit()
            logger.info(f"Message saved: {message_type} - {content[:50]}...")
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            session.rollback()
            raise
        finally:
            session.close()

    def get_recent_messages(self, limit: int = 50, user_id: str = None):
        session = self._Session()
        try:
            query = session.query(History).order_by(History.created_at.desc()).limit(limit)
            if user_id:
                query = query.filter(History.user_id == user_id)
            messages = query.all()
            return [(msg.message_type, msg.content, msg.created_at) for msg in messages]
        finally:
            session.close()

    # User management methods
    def create_user(self, email: str, password: str = None, full_name: str = None, google_id: str = None):
        session = self._Session()
        try:
            hashed_password = None
            if password:
                hashed_password = pwd_context.hash(password)
            
            user = User(
                email=email,
                hashed_password=hashed_password,
                full_name=full_name,
                google_id=google_id,
                is_verified=bool(google_id)  # Google users are pre-verified
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            logger.info(f"User created: {email}")
            return user
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            session.rollback()
            raise
        finally:
            session.close()

    def get_user_by_email(self, email: str):
        session = self._Session()
        try:
            user = session.query(User).filter(User.email == email).first()
            return user
        finally:
            session.close()

    def get_user_by_id(self, user_id: str):
        session = self._Session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            return user
        finally:
            session.close()

    def get_user_by_google_id(self, google_id: str):
        session = self._Session()
        try:
            user = session.query(User).filter(User.google_id == google_id).first()
            return user
        finally:
            session.close()

    def verify_password(self, plain_password: str, hashed_password: str):
        return pwd_context.verify(plain_password, hashed_password)

    def update_user_verification(self, user_id: str, is_verified: bool = True):
        session = self._Session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if user:
                user.is_verified = is_verified
                session.commit()
                logger.info(f"User verification updated: {user.email}")
                return user
            return None
        except Exception as e:
            logger.error(f"Error updating user verification: {e}")
            session.rollback()
            raise
        finally:
            session.close()

    # Email verification methods
    def create_verification_code(self, user_id: str):
        session = self._Session()
        try:
            # Generate a 6-digit verification code
            verification_code = f"{secrets.randbelow(900000) + 100000:06d}"
            expires_at = datetime.utcnow() + timedelta(minutes=15)  # 15 minutes expiry
            
            verification = EmailVerification(
                user_id=user_id,
                verification_code=verification_code,
                expires_at=expires_at
            )
            session.add(verification)
            session.commit()
            session.refresh(verification)
            logger.info(f"Verification code created for user: {user_id}")
            return verification
        except Exception as e:
            logger.error(f"Error creating verification code: {e}")
            session.rollback()
            raise
        finally:
            session.close()

    def verify_code(self, user_id: str, code: str):
        session = self._Session()
        try:
            verification = session.query(EmailVerification).filter(
                EmailVerification.user_id == user_id,
                EmailVerification.verification_code == code,
                EmailVerification.expires_at > datetime.utcnow(),
                EmailVerification.is_used == False
            ).first()
            
            if verification:
                verification.is_used = True
                session.commit()
                logger.info(f"Verification code used for user: {user_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error verifying code: {e}")
            session.rollback()
            raise
        finally:
            session.close() 