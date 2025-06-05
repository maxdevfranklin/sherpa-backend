from fastapi import FastAPI, WebSocket, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import json
from services.database import Database
from services.chatbot import Chatbot
from services.auth import AuthService
from models import (
    UserRegister, UserLogin, GoogleAuthRequest, EmailVerificationRequest,
    ResendVerificationRequest, Token, UserResponse, MessageResponse
)
import logging
from fastapi import WebSocketDisconnect
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
auth_service = AuthService()
security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up application...")
    try:
        db = Database.get_instance()
        logger.info("Database connection established successfully during startup")
    except Exception as e:
        logger.error(f"Failed to establish database connection during startup: {e}")
        logger.warning("Application will continue without database functionality")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")

app = FastAPI(lifespan=lifespan)
chatbot = Chatbot()

# Get allowed origins from environment variable or use defaults
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,https://sherpa-frontend-production.up.railway.app"
).split(",")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get current user from JWT token
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_id = auth_service.verify_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    db = Database.get_instance()
    user = db.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# Optional dependency for websocket authentication
async def get_current_user_optional(token: str = None):
    if not token:
        return None
    
    user_id = auth_service.verify_token(token)
    if user_id is None:
        return None
    
    db = Database.get_instance()
    user = db.get_user_by_id(user_id)
    return user

# Authentication endpoints
@app.post("/auth/register", response_model=MessageResponse)
async def register(user_data: UserRegister):
    try:
        user = auth_service.register_user(
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name
        )
        return MessageResponse(
            message="User registered successfully. Please check your email for verification code.",
            success=True
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.post("/auth/login", response_model=Token)
async def login(user_data: UserLogin):
    user = auth_service.authenticate_user(user_data.email, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email not verified. Please verify your email first.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth_service.create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/auth/google", response_model=Token)
async def google_auth(google_data: GoogleAuthRequest):
    try:
        user = auth_service.verify_google_token(google_data.token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google token"
            )
        
        access_token = auth_service.create_access_token(data={"sub": user.id})
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        logger.error(f"Google auth error: {e}")
        raise HTTPException(status_code=400, detail="Google authentication failed")

@app.post("/auth/verify-email", response_model=MessageResponse)
async def verify_email(verification_data: EmailVerificationRequest):
    try:
        if auth_service.verify_email_code(verification_data.user_id, verification_data.code):
            return MessageResponse(message="Email verified successfully", success=True)
        else:
            raise HTTPException(status_code=400, detail="Invalid or expired verification code")
    except Exception as e:
        logger.error(f"Email verification error: {e}")
        raise HTTPException(status_code=500, detail="Email verification failed")

@app.post("/auth/resend-verification", response_model=MessageResponse)
async def resend_verification(resend_data: ResendVerificationRequest):
    try:
        auth_service.resend_verification_code(resend_data.email)
        return MessageResponse(message="Verification code sent to your email", success=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Resend verification error: {e}")
        raise HTTPException(status_code=500, detail="Failed to send verification code")

@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user = Depends(get_current_user)):
    return current_user

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    try:
        await websocket.accept()
        logger.info("WebSocket connection established")
        
        # Try to get authentication token from query parameters
        token = websocket.query_params.get("token")
        current_user = await get_current_user_optional(token)
        
        # Try to initialize database but don't fail if it doesn't work
        try:
            db = Database.get_instance()
            logger.info("Database connection established for WebSocket session")
        except Exception as e:
            logger.error(f"Database connection failed for WebSocket session: {e}")
            db = None
        
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message_data = json.loads(data)
                logger.info(f"Received message: {message_data.get('content', message_data.get('type', 'unknown'))[:50]}...")
                
                try:
                    # Check if this is a reset command
                    if message_data.get("type") == "reset":
                        logger.info("Resetting chatbot history")
                        chatbot.reset_history()
                        await websocket.send_json({"type": "reset_confirmed", "content": "Chat history has been reset."})
                        continue
                    
                    # Save user message to database if available
                    if db:
                        try:
                            user_id = current_user.id if current_user else None
                            db.save_message("user", message_data["content"], user_id)
                        except Exception as e:
                            logger.error(f"Failed to save user message to database: {e}")
                    
                    # Get response from chatbot
                    response = chatbot.get_response(message_data["content"])
                    
                    # Save bot response to database if available
                    if db:
                        try:
                            user_id = current_user.id if current_user else None
                            db.save_message("bot", response, user_id)
                        except Exception as e:
                            logger.error(f"Failed to save bot message to database: {e}")
                    
                    # Send response back to client
                    await websocket.send_json({"content": response})
                    logger.info(f"Sent response: {response[:50]}...")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await websocket.send_json({"content": "Sorry, there was an error processing your message."})
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")
                await websocket.send_json({"content": "Invalid message format"})
            except Exception as e:
                logger.error(f"Error in message loop: {e}")
                break
            
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        logger.info("WebSocket connection closed")

@app.get("/")
async def root():
    return {"message": "Fashion Guide Chat API with Authentication"} 