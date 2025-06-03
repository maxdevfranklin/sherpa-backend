from typing import TypedDict, Annotated, Sequence
from dotenv import load_dotenv
import os
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Load environment variables
load_dotenv()

# Define the state schema
class ChatState(TypedDict):
    messages: Sequence[HumanMessage | AIMessage | SystemMessage]
    next: str | None
    context: dict

# Initialize the LLM with specific instructions
system_prompt = """You are a compassionate and understanding guide helping families through important life decisions and journeys. Your approach should be:
1. Always be empathetic and patient
2. Listen carefully to their concerns and needs
3. Ask clarifying questions when needed
4. Provide structured, clear guidance while being warm and supportive
5. Acknowledge the emotional aspects of their journey
6. Break down complex decisions into manageable steps
7. Validate their feelings and concerns
8. Offer practical suggestions while being sensitive to their unique situation

Remember that you're helping with significant life decisions, so maintain a balance between being professional and warmly supportive."""

model = ChatAnthropic(model="claude-3-sonnet-20240229")

# Define the chat function
def chat(state: ChatState) -> ChatState:
    messages = state["messages"]
    context = state["context"]
    
    # Add context to the system message if needed
    if context.get("first_interaction", True):
        messages = [
            SystemMessage(content=system_prompt),
            *messages
        ]
        context["first_interaction"] = False
    
    response = model.invoke(messages)
    new_messages = [*messages, response]
    
    return {"messages": new_messages, "next": None, "context": context}

# Create the graph
workflow = StateGraph(ChatState)

# Add the chat node
workflow.add_node("chat", chat)

# Set the entry point
workflow.set_entry_point("chat")

# Add the end condition
workflow.add_edge("chat", END)

# Compile the graph
app = workflow.compile()

def main():
    # Initialize chat state with a warm, empathetic opening
    initial_message = """I'd be happy to get you the information you need, but before I do, do you mind if I ask a few quick questions? That way, I can really understand what's important and make sure I'm helping in the best way possible."""
    
    state = {
        "messages": [HumanMessage(content="Hello, I need some guidance.")],
        "next": None,
        "context": {"first_interaction": True}
    }
    
    # Print the initial welcome message
    print("\nFamily Guide: " + initial_message + "\n")
    
    # Run the chat loop
    while True:
        # Get user input
        user_input = input("You: ")
        if user_input.lower() in ['quit', 'exit', 'bye']:
            print("\nFamily Guide: Thank you for sharing your journey with me. Remember, you're not alone, and you can always come back if you need more guidance. Take care!\n")
            break
            
        # Update messages with user input
        state["messages"].append(HumanMessage(content=user_input))
        
        # Run the graph
        state = app.invoke(state)
        
        # Print the bot's response
        bot_message = state["messages"][-1]
        print(f"\nFamily Guide: {bot_message.content}\n")

if __name__ == "__main__":
    main() 