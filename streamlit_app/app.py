import streamlit as st
import requests
import time
import google.generativeai as genai

API_URL = "http://localhost:8000/tts"  # Adjust if running FastAPI elsewhere
API_TOKEN = "fdavblifgbakdsjbfkasdb12jkabndifjb"
GOOGLE_API_KEY = "AIzaSyCh4Bf5n0T0i72toHsU7joJNtdoELwArbc"

# Configure Google AI
genai.configure(api_key=GOOGLE_API_KEY)

st.title("AI-Powered Text-to-Speech Demo")
st.subheader("Powered by Google Gemini Flash 2.5 Pro + Deepgram TTS")

text = st.text_area("Enter your question or text:", key="text_input", placeholder="Ask me anything...")
mode = st.radio("Select response mode:", ["file", "stream"])

# Enhanced voice selection with latest Deepgram Aura models
voice_options = {
    "Luna (Warm & Natural)": "aura-luna-en",
    "Stella (Professional)": "aura-stella-en", 
    "Athena (Conversational)": "aura-athena-en",
    "Hera (Expressive)": "aura-hera-en",
    "Orion (Deep & Rich)": "aura-orion-en",
    "Arcas (Youthful)": "aura-arcas-en",
    "Perseus (Authoritative)": "aura-perseus-en",
    "Angus (Casual)": "aura-angus-en"
}

selected_voice = st.selectbox("Select Voice Model:", list(voice_options.keys()), index=0)
voice = voice_options[selected_voice]

# Basic Settings
col1, col2 = st.columns(2)
with col1:
    encoding = st.selectbox("Audio Encoding", ["mp3", "linear16", "opus", "flac", "aac", "mulaw", "alaw"], index=0)
    language = st.selectbox("Language", ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"], index=0)

with col2:
    speed = st.slider("Speech Speed", min_value=0.5, max_value=2.0, value=0.8, step=0.1, help="Adjust speaking speed")
    pitch = st.slider("Pitch (semitones)", min_value=-20.0, max_value=20.0, value=0.0, step=0.5, help="Adjust voice pitch")

# Audio Quality Settings
with st.expander("🎵 Audio Quality Settings"):
    col1, col2 = st.columns(2)
    with col1:
        sample_rate = st.selectbox("Sample Rate (Hz)", [16000, 22050, 24000, 44100, 48000], index=4, help="Higher = better quality")
        # Bit rate options depend on encoding
        if encoding == "mp3":
            bit_rate = st.selectbox("Bit Rate (bps)", [32000, 48000], index=1, help="MP3 supports only 32000 or 48000")
        else:
            bit_rate = st.selectbox("Bit Rate (bps)", [96000, 128000, 160000, 192000, 224000, 256000, 320000], index=3, help="Higher = better quality")
    with col2:
        utterance_end_ms = st.slider("Utterance End Silence (ms)", min_value=0, max_value=3000, value=1500, step=100, help="Silence at end of sentences")

# Natural Speech Enhancement
with st.expander("🗣️ Natural Speech Enhancement"):
    col1, col2 = st.columns(2)
    with col1:
        filler_words = st.checkbox("Enable Filler Words", value=True, help="Add natural 'um', 'uh' sounds")
        smart_format = st.checkbox("Smart Formatting", value=True, help="Intelligent text formatting")
    with col2:
        punctuate = st.checkbox("Enhanced Punctuation", value=True, help="Better punctuation pauses")

# Experimental Settings
with st.expander("🧪 Experimental Settings"):
    st.info("These settings are for advanced experimentation")
    callback_url = st.text_input("Callback URL (optional)", help="Webhook for async processing")
    callback_method = st.selectbox("Callback Method", ["POST", "GET"], index=0)

# Settings Summary
with st.expander("📊 Current Settings Summary"):
    settings_dict = {
        "Voice": selected_voice,
        "Speed": speed,
        "Pitch": f"{pitch} semitones",
        "Sample Rate": f"{sample_rate} Hz",
        "Bit Rate": f"{bit_rate} bps",
        "Encoding": encoding.upper(),
        "Language": language,
        "Filler Words": "✓" if filler_words else "✗",
        "Smart Format": "✓" if smart_format else "✗",
        "Punctuation": "✓" if punctuate else "✗",
        "End Silence": f"{utterance_end_ms}ms"
    }
    for key, value in settings_dict.items():
        st.write(f"**{key}:** {value}")

# Initialize session state
if "last_text" not in st.session_state:
    st.session_state.last_text = ""
if "last_stream_time" not in st.session_state:
    st.session_state.last_stream_time = 0
if "last_ai_response" not in st.session_state:
    st.session_state.last_ai_response = ""

def get_ai_response(question):
    """Generate response using Google Gemini Flash 2.5 Pro"""
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # System prompt for human-like speech generation
        system_prompt = """You are a helpful AI assistant that responds in a natural, conversational manner optimized for text-to-speech. 

Follow these guidelines:
- Speak naturally as if having a conversation with a friend
- Use plain text only - no markdown, asterisks, or special formatting
- Use natural speech patterns with appropriate pauses (commas, periods)
- Include conversational fillers like "well", "you know", "actually" when appropriate
- Break down complex information into digestible speech segments
- Use contractions naturally (don't -> don't, you are -> you're)
- Avoid lists with bullet points - instead say "first", "second", "also", "additionally"
- Make it sound like something a human would actually say out loud
- Keep sentences moderately short for natural speech flow

Remember: This will be converted to speech, so write exactly how you would speak to someone."""

        full_prompt = f"{system_prompt}\n\nUser question: {question}"
        
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        st.error(f"AI Error: {e}")
        return None

def make_tts_request(text_to_convert, mode_to_use):
    """Convert text to speech using Deepgram TTS API"""
    headers = {"x-voice-token": API_TOKEN}
    payload = {
        "text": text_to_convert,
        "mode": mode_to_use,
        "voice": voice,
        "encoding": encoding,
        "sample_rate": sample_rate,
        "bit_rate": bit_rate,
        "speed": 0.8,  # Slightly slower for better pacing
        "pitch": pitch,
        "language": language,
        "punctuate": True,  # Ensure punctuation is respected
        "utterance_end_ms": 1500,  # Longer pause at sentence ends
        "filler_words": True,
        "smart_format": True,
        "callback_url": callback_url if callback_url.strip() else None,
        "callback_method": callback_method
    }
    
    try:
        response = requests.post(API_URL, json=payload, headers=headers, stream=(mode_to_use=="stream"))
        if response.status_code != 200:
            try:
                error_detail = response.json().get("detail", response.text)
            except Exception:
                error_detail = response.text
            st.error(f"TTS API Error: {error_detail}")
            return None
        else:
            return response.content
    except Exception as e:
        st.error(f"TTS Error: {e}")
        return None

def stream_ai_and_tts(question):
    """Stream AI response generation and convert to audio chunks in real-time"""
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # System prompt for human-like speech generation
        system_prompt = """You are a helpful AI assistant that responds in a natural, conversational manner optimized for text-to-speech. 

Follow these guidelines:
- Speak naturally as if having a conversation with a friend
- Use plain text only - no markdown, asterisks, or special formatting
- Use natural speech patterns with appropriate pauses (commas, periods)
- Include conversational fillers like "well", "you know", "actually" when appropriate
- Break down complex information into digestible speech segments
- Use contractions naturally (don't -> don't, you are -> you're)
- Avoid lists with bullet points - instead say "first", "second", "also", "additionally"
- Make it sound like something a human would actually say out loud
- Keep sentences moderately short for natural speech flow

Remember: This will be converted to speech, so write exactly how you would speak to someone."""

        full_prompt = f"{system_prompt}\n\nUser question: {question}"
        
        # Generate streaming response from AI
        response_stream = model.generate_content(full_prompt, stream=True)
        
        full_response = ""
        audio_placeholder = st.empty()
        text_placeholder = st.empty()
        
        current_chunk = ""
        chunk_counter = 0
        
        for chunk in response_stream:
            if chunk.text:
                # Clean up any markdown artifacts that might slip through
                clean_text = chunk.text.replace('*', '').replace('#', '').replace('`', '')
                full_response += clean_text
                current_chunk += clean_text
                
                # Update displayed text
                text_placeholder.write(f"**AI Response:** {full_response}")
                
                # Check if we have enough text for TTS (roughly every 800 chars or sentence end)
                if (len(current_chunk) >= 800 and current_chunk.rstrip().endswith(('.', '!', '?'))) or len(current_chunk) >= 1500:
                    chunk_counter += 1
                    
                    # Generate audio for this chunk
                    audio_bytes = make_tts_request(current_chunk.strip(), "stream")
                    if audio_bytes:
                        # Play audio chunk immediately
                        with audio_placeholder.container():
                            st.audio(audio_bytes, format=f"audio/{encoding}", autoplay=True, key=f"chunk_{chunk_counter}")
                    
                    current_chunk = ""
                    
                    # Add a small delay to prevent overwhelming the TTS API
                    time.sleep(0.5)
        
        # Handle remaining text
        if current_chunk.strip():
            chunk_counter += 1
            audio_bytes = make_tts_request(current_chunk.strip(), "stream")
            if audio_bytes:
                with audio_placeholder.container():
                    st.audio(audio_bytes, format=f"audio/{encoding}", autoplay=True, key=f"chunk_final_{chunk_counter}")
        
        return full_response
        
    except Exception as e:
        st.error(f"Streaming Error: {e}")
        return None

# Handle streaming mode - auto-generate AI response and audio when text changes
if mode == "stream":
    st.info("🎤 Streaming mode: AI will respond and generate audio automatically as you type!")
    if text.strip():
        current_time = time.time()
        # Only trigger if text changed and enough time has passed (debounce)
        if (text != st.session_state.last_text and 
            current_time - st.session_state.last_stream_time > 2.0):  # 2 second debounce for AI
            
            st.session_state.last_text = text
            st.session_state.last_stream_time = current_time
            
            with st.spinner("Generating AI response..."):
                ai_response = get_ai_response(text)
                if ai_response:
                    st.session_state.last_ai_response = ai_response
                    st.write("**AI Response:**")
                    st.write(ai_response)
                    
                    with st.spinner("Converting to speech..."):
                        audio_bytes = make_tts_request(ai_response, "stream")
                        if audio_bytes:
                            st.success("Audio streamed!")
                            st.audio(audio_bytes, format=f"audio/{encoding}", autoplay=True)
    
    # Show last AI response if available
    elif st.session_state.last_ai_response and text.strip():
        st.write("**AI Response:**")
        st.write(st.session_state.last_ai_response)
    
    # Auto-refresh for stream mode to detect text changes
    time.sleep(0.1)
    st.rerun()

# Only show manual conversion button for file mode
if mode == "file":
    if st.button("Generate AI Response & Convert to Speech"):
        if not text.strip():
            st.warning("Please enter a question or text.")
        else:
            with st.spinner("Generating AI response..."):
                ai_response = get_ai_response(text)
                if ai_response:
                    st.write("**AI Response:**")
                    st.write(ai_response)
                    
                    with st.spinner("Converting to speech..."):
                        audio_bytes = make_tts_request(ai_response, mode)
                        if audio_bytes:
                            st.success("Audio generated!")
                            st.audio(audio_bytes, format=f"audio/{encoding}")
                            st.download_button("Download Audio", audio_bytes, file_name=f"ai_response.{encoding}", mime=f"audio/{encoding}")
