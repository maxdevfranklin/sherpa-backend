from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import json
from services.database import Database
from services.chatbot import Chatbot
import logging
from fastapi import WebSocketDisconnect
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
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

@app.on_event("startup")
async def startup():
    logger.info("Starting up application...")
    try:
        db = Database.get_instance()
        logger.info("Database connection established successfully during startup")
    except Exception as e:
        logger.error(f"Failed to establish database connection during startup: {e}")
        logger.warning("Application will continue without database functionality")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    try:
        await websocket.accept()
        logger.info("WebSocket connection established")
        
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
                logger.info(f"Received message: {message_data['content'][:50]}...")
                
                try:
                    # Save user message to database if available
                    if db:
                        try:
                            db.save_message("user", message_data["content"])
                        except Exception as e:
                            logger.error(f"Failed to save user message to database: {e}")
                    
                    # Get response from chatbot
                    response = chatbot.get_response(message_data["content"])
                    
                    # Save bot response to database if available
                    if db:
                        try:
                            db.save_message("bot", response)
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
    return {"message": "WebSocket server is running"} 