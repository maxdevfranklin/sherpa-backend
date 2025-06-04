from sqlalchemy import create_engine, Column, String, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

class History(Base):
    __tablename__ = 'history'
    
    id = Column(String, primary_key=True, server_default=text('gen_random_uuid()'))
    message_type = Column(String, nullable=False)
    content = Column(String, nullable=False)
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
            database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:SCoi~IpdVZe6x37NCP.631X9jZubPctR@centerbeam.proxy.rlwy.net:43656/railway')
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

    def save_message(self, message_type: str, content: str):
        session = self._Session()
        try:
            message = History(message_type=message_type, content=content)
            session.add(message)
            session.commit()
            logger.info(f"Message saved: {message_type} - {content[:50]}...")
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            session.rollback()
            raise
        finally:
            session.close()

    def get_recent_messages(self, limit: int = 50):
        session = self._Session()
        try:
            messages = session.query(History).order_by(History.created_at.desc()).limit(limit).all()
            return [(msg.message_type, msg.content, msg.created_at) for msg in messages]
        finally:
            session.close() 