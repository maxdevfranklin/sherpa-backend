from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import json
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

app = FastAPI()

# Enable CORS for React development server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React development server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the LLM
model = ChatAnthropic(model="claude-3-sonnet-20240229")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Send initial message
    initial_message = """I'd be happy to get you the information you need, but before I do, do you mind if I ask a few quick questions? That way, I can really understand what's important and make sure I'm helping in the best way possible."""
    await websocket.send_json({"type": "bot", "content": initial_message})
    
    # Initialize messages
    messages = [
        SystemMessage(content="""You are a compassionate and understanding guide helping families through important life decisions and journeys. Your approach should be:
1. Always be empathetic and patient
2. Listen carefully to their concerns and needs
3. Ask clarifying questions when needed
4. Provide structured, clear guidance while being warm and supportive
5. Acknowledge the emotional aspects of their journey
6. Break down complex decisions into manageable steps
7. Validate their feelings and concerns
8. Offer practical suggestions while being sensitive to their unique situation"""),
        HumanMessage(content="Hello, I need some guidance.")
    ]
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            user_message = json.loads(data)
            
            # Add user message to history
            messages.append(HumanMessage(content=user_message["content"]))
            
            # Get bot response
            response = model.invoke(messages)
            messages.append(response)
            
            # Send response back to client
            await websocket.send_json({
                "type": "bot",
                "content": response.content
            })
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await websocket.close() 