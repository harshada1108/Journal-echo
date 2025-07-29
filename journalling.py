import streamlit as st
from dotenv import load_dotenv
import os
import json
from datetime import datetime
import google.generativeai as genai
import speech_recognition as sr

# Page configuration
st.set_page_config(
    page_title="Journal Echo",
    page_icon="🧘",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .journal-container {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .mentor-message {
        background-color: #e6f7ff;
        padding: 15px;
        border-radius: 15px;
        margin: 10px 0;
        border-left: 4px solid #1890ff;
        color: black;
    }
    .user-message {
        background-color: #f0f2f5;
        padding: 15px;
        border-radius: 15px;
        margin: 10px 0;
        border-left: 4px solid #52c41a;
        color: black;
    }
    .stTextArea textarea {
        border-radius: 10px;
        border: 1px solid #d9d9d9;
    }
    .stButton button {
        border-radius: 20px;
        padding: 5px 20px;
    }
    /* Summary view styles */
    .summary-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        border-left: 4px solid #6c5ce7;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .summary-date {
        color: #6c5ce7;
        font-weight: bold;
        margin-bottom: 10px;
    }
    .summary-text {
        color: #2d3436;
        line-height: 1.6;
    }
    .insights-title {
        color: black;
        font-weight: bold;
        margin-top: 15px;
        margin-bottom: 10px;
    }
    .insight-item {
          color:black;  
        background-color: #f8f9fa;
        padding: 10px 15px;
        border-radius: 8px;
        margin-bottom: 8px;
        border-left: 3px solid #a29bfe;
    }
    .main-title {
        text-align: center;
        color: #2d3436;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# Load environment variables
load_dotenv()

# Configure Gemini API
if "GEMINI_API_KEY" in os.environ:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
else:
    # Try to use the API key from the paste.txt file as fallback
    genai.configure(api_key="AIzaSyAwb3jYZej__F4KJOS7LM6m_jG3BqnSHvA")

# Model configuration
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 65536,
    "response_mime_type": "text/plain",
}

# Load Gemini model
model = genai.GenerativeModel(
    model_name="models/gemini-2.5-pro-exp-03-25",
    generation_config=generation_config,
)

# File paths
JOURNAL_LOG = "journal_entries.json"
SUMMARY_PATH = "journal_summary.json"
TEMP_JOURNAL = "temp_journal.txt"

# Load existing journal data
if os.path.exists(JOURNAL_LOG):
    with open(JOURNAL_LOG, "r") as f:
        journal_data = json.load(f)
else:
    journal_data = []

# Initialize session states
if "session_entries" not in st.session_state:
    st.session_state.session_entries = []

if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])
    # Journaling mentor system prompt
    system_prompt = """
    You are a concise, emotionally intelligent journaling mentor.
    
    Your goal is to:
    - Respond briefly and warmly (1-2 sentences max).
    - Acknowledge the user's feelings with empathy.
    - Gently guide them to reflect deeper or express more.
    - Avoid giving advice or lecturing.
    - Use simple, grounded language.
    
    Always end your response with a gentle question or invitation to reflect more.
    """
    st.session_state.chat.send_message(system_prompt)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "current_mode" not in st.session_state:
    st.session_state.current_mode = "Write on your own"

# Add a flag for clearing input
if "clear_input" not in st.session_state:
    st.session_state.clear_input = False

# Add app view state (journal or summary)
if "app_view" not in st.session_state:
    st.session_state.app_view = "journal"

# Add latest summary state
if "latest_summary" not in st.session_state:
    st.session_state.latest_summary = None

# Add state for echo chat mode
if "echo_chat_mode" not in st.session_state:
    st.session_state.echo_chat_mode = False

# Add state for echo chat history
if "echo_chat_history" not in st.session_state:
    st.session_state.echo_chat_history = []

# Function to generate and save summary
def generate_and_save_summary(entries):
    if not entries:
        return None
    
    # Combine the session into plain text
    combined_text = "\n".join(
        f"{entry['timestamp']} - You: {entry['user_input']}" for entry in entries
    )

    # System prompt for summarization
    system_prompt = """
    You are a journaling assistant. Summarize the user's full journaling session.

    Include:
    - Important events and dates
    - The emotional tone and how it changed
    - Observations about the user's personality and emotional state

    Keep it short (4-6 lines). Write in a friendly, human tone.

    Output only the summary text. Do NOT include any JSON formatting or labels.
    """

    # Generate summary using Gemini
    chat = model.start_chat()
    chat.send_message(system_prompt)
    response = chat.send_message(combined_text)

    # Get the summary from the response
    summary_text = response.text.strip()

    # Format the final flat summary
    summary_entry = {
        "timestamp": datetime.now().isoformat(),
        "summary": summary_text
    }

    # Save to journal_summary.json
    if os.path.exists(SUMMARY_PATH):
        with open(SUMMARY_PATH, "r") as f:
            summaries = json.load(f)
    else:
        summaries = []

    summaries.append(summary_entry)

    with open(SUMMARY_PATH, "w") as f:
        json.dump(summaries, f, indent=2)
    
    return summary_entry

# Function to generate insights from all summaries
def generate_insights(summaries):
    if not summaries:
        return []
    
    # Combine all summaries into a text
    combined_summaries = "\n\n".join([
        f"Date: {datetime.fromisoformat(s['timestamp']).strftime('%Y-%m-%d')}\nSummary: {s['summary']}" 
        for s in summaries
    ])
    
    # Create a prompt for insights
    prompt = """
    Based on these journal summaries, identify 3-5 key insights about:
    1. Recurring themes or patterns
    2. Emotional trends
    3. Potential areas for personal growth
    4. Strengths demonstrated

    Format each insight as a concise bullet point without numbering or prefixes.
    Be specific, thoughtful, and empathetic.
    """
    
    # Generate insights
    chat = model.start_chat()
    chat.send_message(prompt)
    response = chat.send_message(combined_summaries)
    
    # Process the response into a list of insights
    insights = [line.strip() for line in response.text.strip().split('\n') if line.strip()]
    return insights

# Function to load summaries
def load_summaries():
    if os.path.exists(SUMMARY_PATH):
        with open(SUMMARY_PATH, "r") as f:
            summaries = json.load(f)
    else:
        summaries = []
    return summaries

# Function to get latest summary
def get_latest_summary():
    summaries = load_summaries()
    if not summaries:
        return None
    
    # Sort summaries by timestamp
    summaries.sort(key=lambda x: datetime.fromisoformat(x['timestamp'].replace("Z", "+00:00") 
                                                      if x['timestamp'].endswith("Z") 
                                                      else x['timestamp']))
    
    return summaries[-1]

# Function to handle input submission
def submit_entry():
    if st.session_state.mentor_input.strip():
        user_input = st.session_state.mentor_input
        
        # Add user message to chat history
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        # Get response from Gemini
        response = st.session_state.chat.send_message(user_input)
        
        # Add mentor response to chat history
        st.session_state.chat_history.append({"role": "mentor", "content": response.text})
        
        # Save entry
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "mentor_response": response.text
        }
        st.session_state.session_entries.append(entry)
        
        # Set flag to clear the input on next render
        st.session_state.clear_input = True

# Function for echo chat submission
def submit_echo_chat():
    if st.session_state.echo_input.strip():
        user_input = st.session_state.echo_input
        
        # Add user message to echo chat history
        st.session_state.echo_chat_history.append({"role": "user", "content": user_input})
        
        # Save to temp journal
        append_to_temp_journal(user_input)
        
        # Get empathetic response from the echo chat
        response = st.session_state.echo_chat.send_message(user_input)
        
        # Add response to echo chat history
        st.session_state.echo_chat_history.append({"role": "assistant", "content": response.text})
        
        # Set flag to clear the input on next render
        st.session_state.clear_input = True

# Function to handle solo entry submission
def submit_solo_entry():
    if st.session_state.solo_journal.strip():
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_input": st.session_state.solo_journal
        }
        st.session_state.session_entries.append(entry)
        st.success("✅ Entry saved for this session.")
        st.session_state.clear_input = True

# Function to end session
def end_current_session():
    if st.session_state.session_entries:
        # Save session to journal_data
        journal_data.append({
            "session_timestamp": datetime.now().isoformat(),
            "entries": st.session_state.session_entries
        })
        
        with open(JOURNAL_LOG, "w") as f:
            json.dump(journal_data, f, indent=2)
        
        entry_count = len(st.session_state.session_entries)
        st.success(f"📔 Session with {entry_count} entries saved successfully!")
        
        # Generate and save summary
        st.session_state.latest_summary = generate_and_save_summary(st.session_state.session_entries)
        
        # Switch to summary view
        st.session_state.app_view = "summary"
        
        # Reset session entries and chat history
        st.session_state.session_entries = []
        st.session_state.chat_history = []
        st.session_state.clear_input = True
    else:
        st.warning("No entries to save in this session.")

# Start Echo Chat based on journal summaries
def start_echo_chat():
    st.session_state.echo_chat_mode = True
    
    # Initialize Echo Chat with Gemini
    st.session_state.echo_chat = model.start_chat(history=[])
    
    # Reset chat history
    st.session_state.echo_chat_history = []
    
    # Get latest summary
    latest_summary = get_latest_summary()
    
    # Generate empathetic welcome message
    if latest_summary:
        empathetic_response = generate_empathetic_response(latest_summary, st.session_state.echo_chat)
        
        # Add welcome message to chat history
        st.session_state.echo_chat_history.append({"role": "assistant", "content": empathetic_response})
    else:
        # Default welcome if no summary exists
        welcome_msg = "Welcome to Journal Echo! I'm here to listen whenever you're ready to share your thoughts."
        st.session_state.echo_chat_history.append({"role": "assistant", "content": welcome_msg})

# Function to generate empathetic response based on latest summary
def generate_empathetic_response(summary_entry, chat):
    if not summary_entry:
        return "I'm here whenever you're ready to share your thoughts."

    summary = summary_entry.get("summary", "")

    user_prompt = f"""
This is the user's journal summary:
"{summary}"

You are a warm, emotionally intelligent friend.

Your job is to:
- Read the journal summary shared by the user.
- Remember the important incidents and also include them in your response 
- Understand what they're feeling based on what they've been through.
- Respond in a brief, kind, and human way — like a close friend would.
- If they seem sad, be extra gentle and comforting.
- If they're happy, celebrate with them and feel free to joke or be playful.
- End your response with a soft question or invitation to share more if necessary.

Make the user feel safe, seen, and emotionally supported.
Keep things light and friendly — no lecturing, no deep analysis, and definitely no judgment.

Think like a mix of: a close friend, a safe space, and someone who just gets them.
"""

    response = chat.send_message(user_prompt)
    return response.text.strip()

# Function to listen from microphone
def listen_from_mic():
    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    st.info("🎤 Listening... Speak now.")
    
    try:
        with mic as source:
            audio = recognizer.listen(source, timeout=5)
        
        st.info("🔁 Transcribing...")
        text = recognizer.recognize_google(audio)
        return text
    except sr.UnknownValueError:
        st.error("❌ Sorry, couldn't understand you.")
    except sr.RequestError as e:
        st.error(f"⚠ API unavailable: {e}")
    except Exception as e:
        st.error(f"⚠ Error: {e}")
    
    return None

# Function to append to temp journal
def append_to_temp_journal(user_input):
    try:
        with open(TEMP_JOURNAL, "a") as f:
            timestamp = datetime.utcnow().isoformat() + "Z"
            f.write(f"[{timestamp}] {user_input.strip()}\n")
    except Exception as e:
        st.error(f"⚠ Failed to write to journal file: {e}")

# Main app content based on current view
if st.session_state.app_view == "journal":
    # ----- JOURNAL VIEW -----
    
    # Sidebar for app navigation and past entries
    with st.sidebar:
        st.image("https://via.placeholder.com/150x150.png?text=Journal+Echo", width=150)
        st.header("Journal Echo")
        st.markdown("---")
        
        # Past sessions
        if journal_data:
            with st.expander("📚 Past Journal Sessions"):
                for i, session in enumerate(reversed(journal_data)):
                    session_date = datetime.fromisoformat(session["session_timestamp"]).strftime("%B %d, %Y")
                    entries_count = len(session["entries"])
                    st.markdown(f"**Session {len(journal_data)-i}**: {session_date} ({entries_count} entries)")
        
        st.markdown("---")
        st.markdown("Made with ❤️ by Journal Echo")

    # Main app content
    st.title("🧘 Journal Echo")
    st.markdown("### Your personal journaling companion")

    # Echo Chat mode
    if st.session_state.echo_chat_mode:
        st.markdown("#### Chat with Journal Echo")
        
        # Display chat history
        chat_container = st.container()
        with chat_container:
            for message in st.session_state.echo_chat_history:
                if message["role"] == "user":
                    st.markdown(f"""
                    <div class="user-message">
                        <strong>You:</strong><br>{message["content"]}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="mentor-message">
                        <strong>Echo:</strong><br>{message["content"]}
                    </div>
                    """, unsafe_allow_html=True)
        
        # Input method selection
        input_method = st.radio("Choose input method:", ("Text", "Speech"), horizontal=True)
        
        # Handle clear input flag
        if st.session_state.clear_input:
            st.session_state.echo_input = ""
            st.session_state.clear_input = False
        
        if input_method == "Text":
            # Text input
            echo_input = st.text_area("Your message:", height=100, key="echo_input")
            
            submit = st.button("Send", on_click=submit_echo_chat)
        else:
            # Speech input
            if st.button("Start Recording"):
                speech_text = listen_from_mic()
                if speech_text:
                    st.session_state.echo_input = speech_text
                    submit_echo_chat()
        
        # End Echo Chat button
        if st.button("End Echo Chat Session"):
            st.session_state.echo_chat_mode = False
            end_current_session()
    
    else:
        # Regular journal mode selection
        mode = st.radio(
            "Choose your journaling style:",
            ("Write on your own", "Use Journaling Mentor"),
            horizontal=True
        )

        # Update current mode
        if mode != st.session_state.current_mode:
            st.session_state.current_mode = mode
            # Reset chat history when switching modes
            if mode == "Use Journaling Mentor":
                st.session_state.chat_history = []

        # Main content layout
        if mode == "Write on your own":
            # Simple journal entry interface
            with st.container():
                st.markdown("#### Write freely below:")
                
                # Handle clear input flag
                if st.session_state.clear_input:
                    st.session_state.solo_journal = ""
                    st.session_state.clear_input = False
                    
                solo_journal = st.text_area("Your thoughts...", height=200, key="solo_journal")
                
                col1, col2 = st.columns(2)
                with col1:
                    submit = st.button("Save Entry", on_click=submit_solo_entry, use_container_width=True)
                with col2:
                    end_session = st.button("End Session", on_click=end_current_session, use_container_width=True)

        else:  # Use Journaling Mentor mode
            # Chat-based interface
            st.markdown("#### Chat with your Journaling Mentor")
            
            # Display chat history
            chat_container = st.container()
            with chat_container:
                if not st.session_state.chat_history:
                    st.markdown("##### Begin your journaling session by sharing your thoughts below.")
                else:
                    for message in st.session_state.chat_history:
                        if message["role"] == "user":
                            st.markdown(f"""
                            <div class="user-message">
                                <strong>You:</strong><br>{message["content"]}
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div class="mentor-message">
                                <strong>Mentor:</strong><br>{message["content"]}
                            </div>
                            """, unsafe_allow_html=True)
            
            # Handle clear input flag
            if st.session_state.clear_input:
                st.session_state.mentor_input = ""
                st.session_state.clear_input = False
            
            # User input for chat
            mentor_input = st.text_area("Share your thoughts...", height=100, key="mentor_input")
            
            col1, col2 = st.columns(2)
            with col1:
                submit = st.button("Send", on_click=submit_entry, use_container_width=True)
            with col2:
                end_session = st.button("End Chat Session", on_click=end_current_session, use_container_width=True)

else:
    # ----- SUMMARY VIEW -----
    
    # Load all summaries
    summaries = load_summaries()
    
    st.markdown("<h1 class='main-title'>📔 Journal Echo - Your Journey So Far</h1>", unsafe_allow_html=True)
    
    # Show latest summary in a highlighted card
    latest_summary = st.session_state.latest_summary if st.session_state.latest_summary else (summaries[-1] if summaries else None)
    
    if latest_summary:
        latest_date = datetime.fromisoformat(latest_summary["timestamp"]).strftime("%B %d, %Y")
        
        st.markdown("### Latest Session Summary")
        st.markdown(f"""
        <div class="summary-card">
            <div class="summary-date">📆 {latest_date}</div>
            <div class="summary-text">{latest_summary["summary"]}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # COMMENTED TO STOP REFLEXIVE INSIGHTS
        
        # # Generate and display insights
        # with st.spinner("Generating insights from your journal entries..."):
        #     insights = generate_insights(summaries)
        
        # st.markdown("<h3>Reflective Insights</h3>", unsafe_allow_html=True)
        # if insights:
        #     for insight in insights:
        #         st.markdown(f"<div class='insight-item'>{insight}</div>", unsafe_allow_html=True)
        # else:
        #     st.info("Need more journal entries to generate meaningful insights.")
        
        # Show past summaries
        if len(summaries) > 1:
            with st.expander("View Past Summaries"):
                for summary in reversed(summaries[:-1]):  # Skip the latest one as it's already shown
                    date = datetime.fromisoformat(summary["timestamp"]).strftime("%B %d, %Y")
                    st.markdown(f"""
                    <div class="summary-card">
                        <div class="summary-date">📆 {date}</div>
                        <div class="summary-text">{summary["summary"]}</div>
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.warning("No journal summaries available yet.")
    
    # Button to start Echo Chat based on journal summaries
    st.button("Start Echo Chat", on_click=start_echo_chat, use_container_width=True)