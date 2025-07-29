
from dotenv import load_dotenv
import os
import json
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
# Load Gemini model
model = genai.GenerativeModel(
    model_name="models/gemini-2.5-pro-exp-03-25",
    generation_config={
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 65536,
        "response_mime_type": "text/plain",
    },
)

# Load the journal entries
with open("journal_entries.json", "r") as f:
    journal_data = json.load(f)

# Get the last session
latest_session = journal_data[-1]
timestamp = latest_session["session_timestamp"]
entries = latest_session["entries"]

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

# Generate summary using Gemini (correct method)
# The original line caused the KeyError because the `history` parameter in `start_chat`
# was not in the correct format for the Gemini API. This updated code creates a new chat
# and sends the system prompt and user message as individual messages which is the 
# appropriate way to interact with `start_chat`
chat = model.start_chat()
chat.send_message(system_prompt)
response = chat.send_message(combined_text)


# Get the summary from the response
summary_text = response.text.strip()

# Format the final flat summary
summary_entry = {
    "timestamp": timestamp,
    "summary": summary_text
}

# Save to journal_summary.json
summary_path = "journal_summary.json"
if os.path.exists(summary_path):
    with open(summary_path, "r") as f:
        summaries = json.load(f)
else:
    summaries = []

summaries.append(summary_entry)

with open(summary_path, "w") as f:
    json.dump(summaries, f, indent=2)

print("✅ Summary added to journal_summary.json")