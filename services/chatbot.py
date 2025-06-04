from typing import TypedDict, Annotated, Sequence, Literal
from dotenv import load_dotenv
import os
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Define the state schema
class ChatState(TypedDict):
    messages: Sequence[HumanMessage | AIMessage | SystemMessage]
    next: str | None
    context: dict
    community_info: dict | None

# Community information
GRAND_VILLA_INFO = {
    "name": "Grand Villa",
    "description": "Grand Villa is a premier senior living community offering independent living, assisted living, and memory care services. We provide a luxurious lifestyle with resort-style amenities, chef-prepared meals, and engaging activities.",
    "amenities": [
        "Resort-style swimming pool",
        "Fitness center",
        "Beauty salon and barbershop",
        "Restaurant-style dining",
        "Engaging activities and events",
        "24/7 care and support"
    ],
    "care_types": ["Independent Living", "Assisted Living", "Memory Care"],
    "locations": ["Florida", "Georgia", "Alabama"]
}

# Initialize the LLM with specific instructions
system_prompt = """You're a friendly guide helping people find living arrangements. Keep responses brief and conversational.

Initial Message: "I'd be happy to get you the information you need, but before I do, do you mind if I ask a few quick questions? That way, I can really understand what's important and make sure I'm helping in the best way possible."

Follow-up Questions (one at a time):
1. Type of care needed (independent living, assisted living, memory care)
2. Location preferences
3. Budget considerations
4. Specific requirements

Guidelines:
- Always start with the initial message
- Ask one question at a time
- Be warm and friendly
- Keep responses under 2-3 sentences
- Acknowledge responses before asking next question"""

class Chatbot:
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not found. Chatbot will use fallback responses.")
            self.model = None
        else:
            self.model = ChatAnthropic(
                model="claude-3-sonnet-20240229",
                anthropic_api_key=api_key
            )
        
        # Create the graph
        self.workflow = StateGraph(ChatState)
        
        # Add nodes
        self.workflow.add_node("chat", self._chat)
        self.workflow.add_node("recommend_community", self._recommend_community)
        
        # Set the entry point
        self.workflow.set_entry_point("chat")
        
        # Add edges with recursion limit
        self.workflow.add_conditional_edges(
            "chat",
            self._should_recommend_community,
            {
                "recommend": "recommend_community",
                "continue_chat": END  # End the graph after chat
            }
        )
        self.workflow.add_edge("recommend_community", END)  # End after recommendation
        
        # Compile the graph
        self.app = self.workflow.compile()
        
        # Initialize state
        self.state = {
            "messages": [],
            "next": None,
            "context": {"first_interaction": True},
            "community_info": None
        }

    def _should_recommend_community(self, state: ChatState) -> Literal["recommend", "continue_chat"]:
        """Determine if we should recommend a community based on the conversation."""
        messages = state["messages"]
        if not messages:
            return "continue_chat"
            
        # Get the last message content
        last_message = messages[-1]
        
        # Extract message content safely
        message_content = ""
        if isinstance(last_message, (HumanMessage, AIMessage)):
            message_content = last_message.content
        elif isinstance(last_message, list) and last_message:
            if isinstance(last_message[0], (HumanMessage, AIMessage)):
                message_content = last_message[0].content
        
        if message_content:
            message_content = message_content.lower()
            # Check if the user is asking about communities or locations
            community_keywords = ["community", "communities", "place", "facility", "location", "where"]
            if any(keyword in message_content for keyword in community_keywords):
                return "recommend"
        
        return "continue_chat"

    def _recommend_community(self, state: ChatState) -> ChatState:
        """Recommend Grand Villa community."""
        if not self.model:
            return {
                "messages": state["messages"] + [AIMessage(content="I'm sorry, but I'm currently unable to process your request. API Key is not provided.")],
                "next": None,
                "context": state["context"],
                "community_info": None
            }

        # Create a message about Grand Villa
        community_message = f"""I'd like to tell you about Grand Villa, a premier senior living community. {GRAND_VILLA_INFO['description']}

        Key amenities include:
        {', '.join(GRAND_VILLA_INFO['amenities'])}

        Would you like to know more about Grand Villa or would you prefer to explore other options?"""

        return {
            "messages": state["messages"] + [AIMessage(content=community_message)],
            "next": None,
            "context": state["context"],
            "community_info": GRAND_VILLA_INFO
        }

    def _chat(self, state: ChatState) -> ChatState:
        if not self.model:
            return {
                "messages": state["messages"] + [AIMessage(content="I'm sorry, but I'm currently unable to process your request. API Key is not provided.")],
                "next": None,
                "context": state["context"],
                "community_info": state.get("community_info")
            }

        messages = state["messages"]
        context = state["context"]
        
        # Add context to the system message if needed
        if context.get("first_interaction", True):
            messages = [
                SystemMessage(content=system_prompt),
                *messages
            ]
            context["first_interaction"] = False
        
        try:
            response = self.model.invoke(messages)
            new_messages = [*messages, response]
            
            return {
                "messages": new_messages,
                "next": None,
                "context": context,
                "community_info": state.get("community_info")
            }
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return {
                "messages": messages + [AIMessage(content="I apologize, but I encountered an error. Could you please try rephrasing your message?")],
                "next": None,
                "context": context,
                "community_info": state.get("community_info")
            }

    def get_response(self, user_message: str) -> str:
        if not self.model:
            return "I'm sorry, but I'm currently unable to process your request. API Key is not provided."
            
        try:
            # Update messages with user input
            if not isinstance(self.state["messages"], list):
                self.state["messages"] = []
            self.state["messages"].append(HumanMessage(content=user_message))
            
            # Run the graph
            self.state = self.app.invoke(self.state)
            
            # Get the last message content
            last_message = self.state["messages"][-1]
            if isinstance(last_message, (HumanMessage, AIMessage)):
                return last_message.content
            elif isinstance(last_message, list) and last_message:
                return last_message[0].content
            else:
                return "I apologize, but I couldn't process your message properly."
        except Exception as e:
            logger.error(f"Error in get_response: {e}")
            return "I apologize, but I encountered an error. Could you please try again?" 