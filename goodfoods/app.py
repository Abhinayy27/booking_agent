"""
GoodFoods Restaurant Reservation System - Streamlit Frontend
A conversational AI interface for restaurant discovery and booking.
"""

import streamlit as st
import os
import sys

# CRITICAL: Force reload of .env BEFORE any imports
# This solves the Streamlit caching issue where .env isn't reloaded
if "dotenv_loaded" not in st.session_state:
    try:
        # Remove any previously loaded dotenv
        import dotenv

        dotenv.load_dotenv(override=True)  # Force override
        st.session_state.dotenv_loaded = True
    except Exception as e:
        print(f"Error loading .env: {e}")

from backend.agents.client_agent import ClientAgent
from backend.config import Config

# Page Config
st.set_page_config(
    page_title="GoodFoods - AI Restaurant Booking",
    page_icon="🍽️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Custom CSS - Minimalistic, clean design inspired by Reserve AI
st.markdown(
    """
<style>
    /* Import Google Fonts for clean typography */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Main app background - warm beige/cream */
    .stApp {
        background: #f5f1ed;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* All text - clean and readable */
    .stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #2c2c2c !important;
        font-family: 'Inter', sans-serif !important;
    }
    
    /* Chat container - centered and clean */
    .main .block-container {
        max-width: 900px;
        padding-top: 3rem;
        padding-bottom: 3rem;
    }
    
    /* Chat input styling - warm, minimalistic */
    .stChatInput {
        background-color: transparent !important;
        border-top: none !important;
        padding: 1.5rem 0 !important;
        margin-top: 2rem !important;
    }
    
    .stChatInput > div > div {
        background-color: #fef7f0 !important;
        border-radius: 16px !important;
        border: 1px solid #e8dfd7 !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04) !important;
        transition: all 0.2s ease !important;
    }
    
    .stChatInput > div > div:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08) !important;
        border-color: #d4c4b8 !important;
    }
    
    .stChatInput textarea {
        background-color: transparent !important;
        color: #2c2c2c !important;
        border: none !important;
        border-radius: 16px !important;
        padding: 1rem 1.25rem !important;
        font-size: 0.95rem !important;
        font-family: 'Inter', sans-serif !important;
        line-height: 1.5 !important;
    }
    
    .stChatInput textarea::placeholder {
        color: #9d8b7e !important;
        opacity: 1 !important;
        font-weight: 400 !important;
    }
    
    .stChatInput textarea:focus {
        background-color: transparent !important;
        outline: none !important;
        box-shadow: none !important;
    }
    
    .stChatInput button {
        background: linear-gradient(135deg, #e89b7e 0%, #e57b5a 100%) !important;
        color: white !important;
        border-radius: 12px !important;
        border: none !important;
        padding: 0.5rem !important;
        width: 3rem !important;
        height: 3rem !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 6px rgba(229, 123, 90, 0.25) !important;
        margin-right: 0.5rem !important;
    }
    
    .stChatInput button:hover {
        background: linear-gradient(135deg, #e57b5a 0%, #d96b4a 100%) !important;
        box-shadow: 0 4px 10px rgba(229, 123, 90, 0.35) !important;
        transform: scale(1.05) !important;
    }
    
    .stChatInput button svg {
        width: 1.2rem !important;
        height: 1.2rem !important;
    }
    
    /* Chat messages - minimalistic cards */
    .stChatMessage {
        margin-bottom: 1.5rem !important;
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
    }
    
    /* Assistant message - warm beige card */
    .stChatMessage[data-testid="assistant"] {
        background: #fef7f0 !important;
        border-radius: 16px !important;
        padding: 1.25rem 1.5rem !important;
        border: 1px solid #f0e6dc !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04) !important;
        transition: all 0.2s ease;
    }
    
    .stChatMessage[data-testid="assistant"]:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06) !important;
    }
    
    /* User message - subtle and clean */
    .stChatMessage[data-testid="user"] {
        background: white !important;
        border-radius: 16px !important;
        padding: 1rem 1.25rem !important;
        border: 1px solid #e8e5e1 !important;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03) !important;
    }
    
    /* Avatar circles - minimalistic */
    .stChatMessage [data-testid="chatAvatarIcon-assistant"] {
        background: linear-gradient(135deg, #e89b7e 0%, #e57b5a 100%) !important;
        border-radius: 50% !important;
        width: 36px !important;
        height: 36px !important;
    }
    
    .stChatMessage [data-testid="chatAvatarIcon-user"] {
        background: #2c2c2c !important;
        border-radius: 50% !important;
        width: 36px !important;
        height: 36px !important;
    }
    
    /* Ensure message text is dark */
    .stChatMessage .stMarkdown {
        color: #212529 !important;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background-color: #ffffff;
    }
    
    /* Button styling - card-like for suggestions */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        background-color: white;
        color: #2c2c2c;
        border: 1px solid #e8dfd7;
        padding: 1.25rem 1rem;
        font-weight: 400;
        font-family: 'Inter', sans-serif;
        font-size: 0.9rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
        transition: all 0.2s ease;
        text-align: center;
        line-height: 1.6;
        white-space: pre-line;
    }
    
    .stButton>button:hover {
        background-color: #fefcfa;
        border-color: #d4c4b8;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        transform: translateY(-2px);
    }
    
    /* Sidebar buttons - different style */
    [data-testid="stSidebar"] .stButton>button {
        background-color: #667eea;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        text-align: left;
        white-space: normal;
    }
    
    [data-testid="stSidebar"] .stButton>button:hover {
        background-color: #764ba2;
        transform: none;
    }
    
    /* Caption text - make it visible */
    .stCaption {
        color: #666 !important;
        font-size: 0.85rem;
    }
    
    /* Footer */
    footer {
        visibility: hidden;
    }
    
    /* Ensure all Streamlit text elements are dark */
    .element-container, .stText, .stMarkdownContainer {
        color: #212529 !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Initialize session state
if "agent" not in st.session_state:
    try:
        st.session_state.agent = ClientAgent()
        st.session_state.initialized = True
    except Exception as e:
        st.session_state.initialized = False
        st.session_state.init_error = str(e)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Welcome to GoodFoods! 🍽️\n\nI'm your AI concierge, and I can help you:\n- Find restaurants based on cuisine, location, price, and ambiance\n- Make reservations\n- Modify or cancel existing bookings\n\nHow can I help you today?",
        }
    ]

# Sidebar
with st.sidebar:
    st.title("🍽️ GoodFoods")
    st.markdown("### Federated Agent Network")
    st.markdown("---")

    st.markdown("**Connected Agents:**")
    st.success("✅ Client Agent (Orchestrator)")
    st.success("✅ Search Agent (Read-Only)")
    st.success("✅ Booking Agent (Transactional)")

    st.markdown("---")

    # Configuration status - read DIRECTLY from environment every time
    st.markdown("**Configuration:**")

    # Force fresh read from environment
    api_key = os.getenv("OPENAI_API_KEY")

    if api_key:
        st.success("✅ OpenAI API Connected")
        st.caption(f"Model: {os.getenv('OPENAI_MODEL', 'gpt-4o-mini')}")
        # Show first few chars for verification
        st.caption(f"API Key: {api_key[:10]}...{api_key[-4:]}")
    else:
        st.warning("⚠️ OpenAI API Key not set")
        st.caption("Checking environment...")

        # Debug information
        env_file_exists = os.path.exists(".env")
        st.caption(f"✓ .env file exists: {env_file_exists}")

        if env_file_exists:
            try:
                with open(".env", "r") as f:
                    content = f.read()
                    has_key = "OPENAI_API_KEY" in content
                    st.caption(f"✓ OPENAI_API_KEY in .env: {has_key}")
            except Exception as e:
                st.caption(f"Error reading .env: {e}")

        # Check if it's an import issue
        try:
            from dotenv import load_dotenv

            result = load_dotenv(override=True)
            st.caption(f"✓ .env reloaded: {result}")

            # Try again after reload
            api_key_after = os.getenv("OPENAI_API_KEY")
            if api_key_after:
                st.success("✅ API Key loaded! Refresh the page.")
            else:
                st.error("API Key still not found after reload")
        except ImportError:
            st.error("python-dotenv not installed")

    st.markdown("---")

    # Reset conversation button
    if st.button("🔄 Reset Conversation", use_container_width=True):
        st.session_state.agent.reset_conversation()
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Conversation reset! How can I help you find a restaurant today?",
            }
        ]
        st.rerun()

    # Example queries - styled like the reference image
    st.markdown(
        """
        <div style="margin: 1.5rem 0 1rem 0;">
            <p style="font-size: 0.9rem; color: #6b6560; margin-bottom: 1rem; font-weight: 400;">
                Or try one of these:
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    example_queries = [
        ("📍", "French restaurant downtown"),
        ("📅", "Date night this Saturday"),
        ("👥", "Group dinner for 8"),
    ]

    # Create 3 columns for horizontal layout
    cols = st.columns(3)

    for idx, (icon, query) in enumerate(example_queries):
        with cols[idx]:
            # Create custom card-style button
            if st.button(
                f"{icon}\n\n{query}",
                key=f"example_{query}",
                use_container_width=True,
            ):
                st.session_state.example_query = query
                st.rerun()

# Main Header - Minimal and elegant
st.markdown(
    """
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1 style="font-size: 2rem; font-weight: 600; color: #2d2d2d; margin-bottom: 0.5rem;">
            🍽️ GoodFoods
        </h1>
        <p style="font-size: 1rem; color: #6b6b6b; font-weight: 400;">
            AI Restaurant Booking Agent
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Check initialization
if not st.session_state.get("initialized", False):
    st.error("⚠️ Failed to initialize the agent system.")
    if "init_error" in st.session_state:
        st.error(f"Error: {st.session_state.init_error}")
    st.info("Please check your configuration and ensure OPENAI_API_KEY is set.")

    # Offer a reload button
    if st.button("🔄 Try Reloading App"):
        st.rerun()

    st.stop()

# Display Chat History
chat_container = st.container()
with chat_container:
    for message in st.session_state.messages:
        role = message["role"]
        content = message["content"]

        with st.chat_message(role):
            st.markdown(content)

            # Minimal caption for assistant
            if role == "assistant":
                st.caption("🤖 Jarvis")

# User Input - Always show chat input
user_input = st.chat_input("Ask, Search or Chat...")

# Check if user has selected an example query
if "example_query" in st.session_state:
    user_input = st.session_state.example_query
    del st.session_state.example_query

if user_input:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Display user message
    with st.chat_message("user"):
        st.markdown(user_input)

    # Generate response with loading indicator
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = st.session_state.agent.process_message(user_input)
                st.markdown(response)

                # Minimal caption
                st.caption("🤖 Jarvis")

            except Exception as e:
                error_msg = f"I encountered an error: {str(e)}. Please try again."
                st.error(error_msg)
                response = error_msg

        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})

        # Rerun to show chat input again
        st.rerun()

# Footer - minimal
st.markdown(
    """
    <div style='text-align: center; color: #9b9b9b; padding: 2rem 0 1rem 0; font-size: 0.85rem;'>
        <p>Powered by AI Agent Network · GoodFoods © 2025</p>
    </div>
    """,
    unsafe_allow_html=True,
)
