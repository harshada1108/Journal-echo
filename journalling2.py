import streamlit as st
from dotenv import load_dotenv
import os
import time
import json
from datetime import datetime
import google.generativeai as genai
import speech_recognition as sr
from difflib import SequenceMatcher

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
    .special-message {
        background-color: #fff8e1;
        padding: 15px;
        border-radius: 15px;
        margin: 15px 0;
        border-left: 4px solid #ffa000;
        color: black;
    }
</style>
""", unsafe_allow_html=True)

# Load environment variables
load_dotenv()

# Configure Gemini API
if "GEMINI_API_KEY" in os.environ:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
else:
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

if "clear_input" not in st.session_state:
    st.session_state.clear_input = False

if "app_view" not in st.session_state:
    st.session_state.app_view = "journal"

if "latest_summary" not in st.session_state:
    st.session_state.latest_summary = None

if "echo_chat_mode" not in st.session_state:
    st.session_state.echo_chat_mode = False

if "echo_chat_history" not in st.session_state:
    st.session_state.echo_chat_history = []

if "echo_chat" not in st.session_state:
    st.session_state.echo_chat = None

# Add state for reflection and letter results
if "reflection_result" not in st.session_state:
    st.session_state.reflection_result = None

if "letter_result" not in st.session_state:
    st.session_state.letter_result = None

# Add state to show special message
if "show_special_message" not in st.session_state:
    st.session_state.show_special_message = False
    st.session_state.special_message_type = None

# Function to generate and save summary
def generate_and_save_summary(entries):
    if not entries:
        return None
    
    combined_text = "\n".join(
        f"{entry['timestamp']} - You: {entry['user_input']}" for entry in entries
    )

    system_prompt = """
    You are a journaling assistant. Summarize the user's full journaling session.

    Include:
    - Important events and dates
    - The emotional tone and how it changed
    - Observations about the user's personality and emotional state

    Keep it short (4-6 lines). Write in a friendly, human tone.

    Output only the summary text. Do NOT include any JSON formatting or labels.
    """

    chat = model.start_chat()
    chat.send_message(system_prompt)
    response = chat.send_message(combined_text)

    summary_text = response.text.strip()

    summary_entry = {
        "timestamp": datetime.now().isoformat(),
        "summary": summary_text
    }

    if os.path.exists(SUMMARY_PATH):
        with open(SUMMARY_PATH, "r") as f:
            summaries = json.load(f)
    else:
        summaries = []

    summaries.append(summary_entry)

    with open(SUMMARY_PATH, "w") as f:
        json.dump(summaries, f, indent=2)
    
    return summary_entry

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
    
    summaries.sort(key=lambda x: datetime.fromisoformat(x['timestamp'].replace("Z", "+00:00") 
                                                      if x['timestamp'].endswith("Z") 
                                                      else x['timestamp']))
    
    return summaries[-1]

# Function to handle input submission
def submit_entry():
    if st.session_state.mentor_input.strip():
        user_input = st.session_state.mentor_input
        
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        response = st.session_state.chat.send_message(user_input)
        
        st.session_state.chat_history.append({"role": "mentor", "content": response.text})
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "mentor_response": response.text
        }
        st.session_state.session_entries.append(entry)
        
        st.session_state.clear_input = True

# Function for echo chat submission
def submit_echo_chat():
    if st.session_state.echo_input.strip():
        user_input = st.session_state.echo_input
        
        st.session_state.echo_chat_history.append({"role": "user", "content": user_input})
        
        append_to_temp_journal(user_input)
        
        response = st.session_state.echo_chat.send_message(user_input)
        
        st.session_state.echo_chat_history.append({"role": "assistant", "content": response.text})
        
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
        journal_data.append({
            "session_timestamp": datetime.now().isoformat(),
            "entries": st.session_state.session_entries
        })
        
        with open(JOURNAL_LOG, "w") as f:
            json.dump(journal_data, f, indent=2)
        
        entry_count = len(st.session_state.session_entries)
        st.success(f"📔 Session with {entry_count} entries saved successfully!")
        
        st.session_state.latest_summary = generate_and_save_summary(st.session_state.session_entries)
        
        # Reset session state
        st.session_state.app_view = "summary"
        st.session_state.session_entries = []
        st.session_state.chat_history = []
        st.session_state.clear_input = True
        st.session_state.echo_chat_mode = False
    else:
        st.warning("No entries to save in this session.")

# Generate self-reflection using Gemini directly
def generate_self_reflection():
    # Load journal summaries
    if os.path.exists(SUMMARY_PATH):
        with open(SUMMARY_PATH, "r") as f:
            summaries = json.load(f)
    else:
        return "No journal entries found to generate a reflection."
    
    # Create reflection chat with system prompt
    reflection_chat = model.start_chat(history=[])
    system_prompt = """
    You are a gentle, emotionally intelligent journaling assistant reviewing someone's past journal entries.

    Your role is to:

    Reflect thoughtfully on the collection of entries from a first-person point of view, as if you're helping them understand their own patterns and emotions.

    Identify the overall emotional tone, recurring themes, habits, or subtle insights.

    Provide a warm, concise reflection (4–6 sentences).

    Avoid summarizing. Instead, offer thoughtful self-awareness or emotional insight.

    Use soft, grounded language. Do not give advice.
    """
    reflection_chat.send_message(system_prompt)
    
    # Combine all summaries into a single prompt
    combined_summaries = "\n\n".join(
        f"{entry.get('timestamp', 'Unknown time')}: {summary}" 
        for entry in summaries if (summary := entry.get('summary', ''))
    )
    
    # Generate reflection
    response = reflection_chat.send_message(f"Here are my recent journal entries:\n\n{combined_summaries}")
    
    return response.text.strip()

# Function to check similarity between strings
def is_similar(a, b, threshold=0.6):
    return SequenceMatcher(None, a, b).ratio() > threshold

# Generate letter from past using Gemini directly
def generate_letter_from_past():
    # Load journal summaries
    if os.path.exists(SUMMARY_PATH):
        with open(SUMMARY_PATH, "r") as f:
            entries = json.load(f)
    else:
        return "No journal entries found to generate a letter."
    
    if not entries or len(entries) < 2:
        return "You need at least two journal entries to receive a letter from your past self."
    
    # Create letter chat with system prompt
    letter_chat = model.start_chat(history=[])
    system_prompt = """
    You are a gentle, emotionally intelligent journaling assistant.

    Your role is to:
    - Read a collection of past journal entry summaries.
    - Find those that carry a similar emotional mood or tenderness to the most recent one.
    - Write a heartfelt, grounding letter *from the voice of the past self*, speaking gently to the present self.
    - Use a second-person point of view, as if past-you is reminding present-you of something you've already lived through and understood.
    - Occasionally, include a soft memory or moment from one of the past summaries—perhaps a feeling, a phrase, or even a date (only if it flows naturally).
    - Keep the letter short, not more than 10–15 lines. Focus on emotional resonance, not explanation.
    - Use poetic or affectionate language if it feels right—but stay grounded and real.

    Do not summarize or reflect. Just write the letter, as if you're gently whispering from the past.
    """
    letter_chat.send_message(system_prompt)
    
    # Extract the latest summary
    latest_entry = entries[-1]
    latest_summary = latest_entry.get("summary", "")
    
    # Find similar summaries
    similar_entries = [
        f"{entry.get('timestamp', '')}: {entry.get('summary', '')}"
        for entry in entries[:-1]
        if is_similar(latest_summary, entry.get("summary", ""))
    ]
    
    # Always include the latest one for context
    all_relevant_summaries = similar_entries + [f"{latest_entry.get('timestamp', '')}: {latest_summary}"]
    
    # Format the summaries into a message
    summaries_block = "\n\n".join(all_relevant_summaries)
    
    # Generate letter
    prompt = f"""
    Here are some emotionally connected journal summaries:

    {summaries_block}

    Write a short, heartfelt letter (under 15 lines) from past-you to present-you.
    Let it carry warmth and quiet understanding. If it feels natural, gently reference a date or a moment from the past.
    """
    
    response = letter_chat.send_message(prompt)
    
    return response.text.strip()

# Function to show reflection
def show_reflection():
    st.session_state.reflection_result = generate_self_reflection()
    st.session_state.show_special_message = True
    st.session_state.special_message_type = "reflection"

# Function to show letter from past
def show_letter():
    st.session_state.letter_result = generate_letter_from_past()
    st.session_state.show_special_message = True
    st.session_state.special_message_type = "letter"

# Function to close special message
def close_special_message():
    st.session_state.show_special_message = False
    st.session_state.special_message_type = None

# Start Echo Chat function - FIXED VERSION
def start_echo_chat():
    # First, set the flag to enable echo chat mode
    st.session_state.echo_chat_mode = True
    
    # Set the app view to journal to ensure we're on the right page
    st.session_state.app_view = "journal"
    
    # Initialize a new chat session
    st.session_state.echo_chat = model.start_chat(history=[])
    
    # Clear the existing echo chat history
    st.session_state.echo_chat_history = []
    
    # Get the latest summary for context
    latest_summary = get_latest_summary()
    
    # Generate a welcome message based on summary
    if latest_summary:
        empathetic_response = generate_empathetic_response(latest_summary, st.session_state.echo_chat)
        st.session_state.echo_chat_history.append({"role": "assistant", "content": empathetic_response})
    else:
        welcome_msg = "Welcome to Journal Echo! I'm here to listen whenever you're ready to share your thoughts."
        st.session_state.echo_chat_history.append({"role": "assistant", "content": welcome_msg})
    
    # Reset the show_special_message flag
    st.session_state.show_special_message = False

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
# def listen_from_mic():
#     recognizer = sr.Recognizer()
#     mic = sr.Microphone()

#     st.info("🎤 Listening... Speak now.")
    
#     try:
#         with mic as source:
#             audio = recognizer.listen(source, timeout=5)
        
#         st.info("🔁 Transcribing...")
#         text = recognizer.recognize_google(audio)
#         return text
#     except sr.UnknownValueError:
#         st.error("❌ Sorry, couldn't understand you.")
#     except sr.RequestError as e:
#         st.error(f"⚠ API unavailable: {e}")
#     except Exception as e:
#         st.error(f"⚠ Error: {e}")
    
#     return None

# Function to listen from microphone
# def listen_from_mic():
#     recognizer = sr.Recognizer()
#     mic = sr.Microphone()
    
#     # Create a placeholder for status messages
#     status_placeholder = st.empty()
#     status_placeholder.info("🎤 Listening... Speak now.")
    
#     # Use columns for start and stop buttons
#     col1, col2 = st.columns(2)
    
#     # Session state to track recording status
#     if "is_recording" not in st.session_state:
#         st.session_state.is_recording = False
        
#     try:
#         with mic as source:
#             # Adjust for ambient noise
#             recognizer.adjust_for_ambient_noise(source, duration=1)
            
#             # Set longer timeout
#             audio = recognizer.listen(source, timeout=10, phrase_time_limit=30)
        
#         status_placeholder.info("🔁 Transcribing...")
#         text = recognizer.recognize_google(audio)
#         status_placeholder.success("✅ Transcription complete!")
#         return text
#     except sr.WaitTimeoutError:
#         status_placeholder.error("❌ Timeout: No speech detected. Please try again.")
#     except sr.UnknownValueError:
#         status_placeholder.error("❌ Sorry, couldn't understand you.")
#     except sr.RequestError as e:
#         status_placeholder.error(f"⚠ API unavailable: {e}")
#     except Exception as e:
#         status_placeholder.error(f"⚠ Error: {e}")
    
#     return None

def listen_from_mic():
    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    
    # Create a placeholder for status messages
    status_placeholder = st.empty()
    
    # Initialize recording state if not exists
    if "recording_active" not in st.session_state:
        st.session_state.recording_active = False
    
    # Set recording as active
    st.session_state.recording_active = True
    status_placeholder.info("🎤 Listening... Speak now.")
    
    try:
        with mic as source:
            # Adjust for ambient noise
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            
            # Start listening in a way that can be interrupted
            audio = None
            
            # This is where we'd ideally use threading, but Streamlit doesn't handle this well
            # Instead we'll use a timeout approach that can be checked against the state
            start_time = time.time()
            max_duration = 30  # Maximum recording time in seconds
            
            while st.session_state.recording_active and (time.time() - start_time) < max_duration:
                try:
                    # Short timeout to allow checking the state frequently
                    audio = recognizer.listen(source, timeout=1, phrase_time_limit=5)
                    break  # If we got audio, break out of the loop
                except sr.WaitTimeoutError:
                    # Keep waiting if we're still recording
                    continue
            
            if not audio:
                if not st.session_state.recording_active:
                    status_placeholder.warning("⚠️ Recording stopped by user.")
                else:
                    status_placeholder.error("❌ No speech detected within timeout period.")
                return None
            
            # Process the audio
            status_placeholder.info("🔁 Transcribing...")
            text = recognizer.recognize_google(audio)
            status_placeholder.success(f"✅ Transcribed: \"{text}\"")
            return text
            
    except sr.UnknownValueError:
        status_placeholder.error("❌ Sorry, couldn't understand you.")
    except sr.RequestError as e:
        status_placeholder.error(f"⚠ API unavailable: {e}")
    except Exception as e:
        status_placeholder.error(f"⚠ Error: {e}")
    finally:
        # Always reset the recording state
        st.session_state.recording_active = False
    
    return None

# Function to append to temp journal
def append_to_temp_journal(user_input):
    try:
        with open(TEMP_JOURNAL, "a") as f:
            timestamp = datetime.utcnow().isoformat() + "Z"
            f.write(f"[{timestamp}] {user_input.strip()}\n")
    except Exception as e:
        st.error(f"⚠ Failed to write to journal file: {e}")

# Return to journal mode
def return_to_journal_mode():
    st.session_state.app_view = "journal"
    st.session_state.echo_chat_mode = False

# Main app content based on current view
if st.session_state.app_view == "journal":
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
        
        # Special message container for reflection or letter
        if st.session_state.show_special_message:
            with st.container():
                if st.session_state.special_message_type == "reflection":
                    st.markdown(f"""
                    <div class="special-message">
                        <strong>🔮 Self-Reflection:</strong><br>{st.session_state.reflection_result}
                    </div>
                    """, unsafe_allow_html=True)
                elif st.session_state.special_message_type == "letter":
                    st.markdown(f"""
                    <div class="special-message">
                        <strong>💌 Letter from Your Past Self:</strong><br>{st.session_state.letter_result}
                    </div>
                    """, unsafe_allow_html=True)
                
                close_button = st.button("Close", on_click=close_special_message)
        
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
            # if st.button("Start Recording"):
            #     speech_text = listen_from_mic()
            #     if speech_text:
            #         st.session_state.echo_input = speech_text
            #         submit_echo_chat()
            if input_method == "Speech":
                col1, col2 = st.columns(2)
                
                # Show appropriate button based on recording state
                if "recording_active" not in st.session_state:
                    st.session_state.recording_active = False
                
                with col1:
                    if not st.session_state.recording_active:
                        if st.button("Start Recording"):
                            speech_text = listen_from_mic()
                            if speech_text:
                                st.session_state.echo_input = speech_text
                                submit_echo_chat()
                
                with col2:
                    if st.session_state.recording_active:
                        if st.button("Stop Recording"):
                            # Set flag to stop recording
                            st.session_state.recording_active = False
                            st.info("Recording stopped.")
        
        # Reflection and Letter buttons displayed side by side
        col1, col2 = st.columns(2)
        with col1:
            st.button("📝 Self-Reflection", on_click=show_reflection, use_container_width=True)
        with col2:
            st.button("💌 Letter from Past", on_click=show_letter, use_container_width=True)
        
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
        
        # Show past summaries
        if len(summaries) > 1:
            with st.expander("View Past Summaries"):
                for summary in reversed(summaries[:-1]):
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
    st.button("Start Echo Chat", on_click=start_echo_chat, key="start_echo_chat_button", use_container_width=True)
    
    # Button to return to regular journal mode
    st.button("Return to Journal", on_click=return_to_journal_mode, use_container_width=True)