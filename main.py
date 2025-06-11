from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import httpx
import tempfile
import os
from typing import Optional
import logging
import re
from io import BytesIO
import zipfile
import asyncio

app = FastAPI()

VOICE_TOKEN = os.getenv("VOICE_TOKEN")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
DEEPGRAM_TTS_URL = "https://api.deepgram.com/v1/speak"

class TTSRequest(BaseModel):
    text: str
    mode: Optional[str] = "file"  # 'file' or 'stream'
    voice: Optional[str] = "aura-luna-en"  # Latest high-quality Deepgram voice
    encoding: Optional[str] = "mp3"  # Default encoding
    sample_rate: Optional[int] = 48000  # Higher sample rate for better quality
    bit_rate: Optional[int] = 192000  # Higher bit rate for better quality
    # Advanced tuning options
    speed: Optional[float] = 0.7  # Speech speed (0.5 to 2.0)
    pitch: Optional[float] = 0.0  # Pitch adjustment (-20.0 to 20.0 semitones)
    language: Optional[str] = "en"  # Language code
    punctuate: Optional[bool] = True  # Add punctuation pauses
    utterance_end_ms: Optional[int] = 1000  # Silence at end of utterances
    filler_words: Optional[bool] = True  # Natural filler words
    smart_format: Optional[bool] = True  # Intelligent formatting
    callback_url: Optional[str] = None  # Webhook callback
    callback_method: Optional[str] = "POST"  # Webhook method

async def fetch_tts_audio(text, voice, encoding, sample_rate=None, bit_rate=None, 
                         speed=None, pitch=None, language=None, punctuate=None,
                         utterance_end_ms=None, filler_words=None, smart_format=None,
                         callback_url=None, callback_method=None):
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Enhanced payload for more human-like speech
    payload = {"text": text}
    
    # Add enhanced parameters for more natural speech
    params = {}
    if voice and voice.strip():
        params["model"] = voice.strip()
    if encoding and encoding.strip():
        params["encoding"] = encoding.strip()
    
    # Only add sample_rate for encodings that support it (not mp3, aac, opus)
    if sample_rate and encoding and encoding.lower() not in ["mp3", "aac", "opus"]:
        params["sample_rate"] = sample_rate
    
    # Only add bit_rate for encodings that support it
    if bit_rate and encoding and encoding.lower() in ["mp3", "aac", "opus"]:
        # MP3 only supports specific bit rates
        if encoding.lower() == "mp3":
            # Ensure MP3 bit rate is valid (32000 or 48000)
            if bit_rate not in [32000, 48000]:
                bit_rate = 48000  # Default to 48000 for better quality
        params["bit_rate"] = bit_rate
    
    if speed is not None:
        params["speed"] = speed
    if pitch is not None:
        params["pitch"] = pitch
    if language:
        params["language"] = language
    if punctuate is not None:
        params["punctuate"] = str(punctuate).lower()
    if utterance_end_ms is not None:
        params["utterance_end_ms"] = utterance_end_ms
    # Enhanced filler words configuration for more natural speech
    if filler_words is not None and filler_words:
        params["filler_words"] = "true"
        # Add additional parameters for more natural speech patterns
        params["disfluencies"] = "true"  # Enable speech disfluencies
        params["hesitations"] = "true"   # Enable hesitations like "um", "uh"
    elif filler_words is False:
        params["filler_words"] = "false"
        params["disfluencies"] = "false"
        params["hesitations"] = "false"
    
    if smart_format is not None:
        params["smart_format"] = str(smart_format).lower()
    if callback_url:
        params["callback_url"] = callback_url
    if callback_method:
        params["callback_method"] = callback_method.lower()
    
    # Set container parameter based on encoding
    if encoding and encoding.strip():
        if encoding.lower() == "mp3":
            # MP3 uses no container parameter or can be omitted
            pass  # Don't set container for MP3
        elif encoding.lower() == "wav":
            params["container"] = "wav"
        elif encoding.lower() == "ogg":
            params["container"] = "ogg"
    
    # Log the payload for debugging
    logging.info(f"Sending payload to Deepgram: {payload}")
    logging.info(f"Sending params to Deepgram: {params}")
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            DEEPGRAM_TTS_URL, 
            headers=headers, 
            json=payload,
            params=params
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logging.error(f"Deepgram API error: {exc.response.status_code} - {exc.response.text}")
            raise HTTPException(status_code=502, detail=f"Deepgram API error: {exc.response.text}")
        return response.content

def clean_text_for_speech(text):
    """Clean text to make it more suitable for speech synthesis"""
    # Remove markdown artifacts
    text = re.sub(r'\*+', '', text)  # Remove asterisks
    text = re.sub(r'#+\s*', '', text)  # Remove headers
    text = re.sub(r'`+', '', text)  # Remove code blocks
    text = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', text)  # Convert links to text
    text = re.sub(r'_{2,}', '', text)  # Remove underscores
    
    # Fix common issues for speech
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    text = re.sub(r'([.!?])\s*([A-Z])', r'\1 \2', text)  # Ensure space after punctuation
    
    return text.strip()

def chunk_text(text, max_chars=1800):  # Reduced from 2000 for safety
    """
    Split text into chunks of max_chars while preserving sentence boundaries
    """
    # Clean text first
    text = clean_text_for_speech(text)
    
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Split by sentences first
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    for sentence in sentences:
        # If single sentence is too long, split by words
        if len(sentence) > max_chars:
            words = sentence.split()
            word_chunk = ""
            for word in words:
                if len(word_chunk + " " + word) <= max_chars:
                    word_chunk += " " + word if word_chunk else word
                else:
                    if word_chunk:
                        chunks.append(word_chunk.strip())
                    word_chunk = word
            if word_chunk:
                chunks.append(word_chunk.strip())
        else:
            # Check if adding this sentence exceeds limit
            if len(current_chunk + " " + sentence) <= max_chars:
                current_chunk += " " + sentence if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

async def fetch_tts_audio_chunk(text_chunk, voice, encoding, sample_rate=None, bit_rate=None, 
                               speed=None, pitch=None, language=None, punctuate=None,
                               utterance_end_ms=None, filler_words=None, smart_format=None,
                               callback_url=None, callback_method=None):
    """Generate audio for a single text chunk with throttling"""
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Clean the text chunk
    clean_chunk = clean_text_for_speech(text_chunk)
    payload = {"text": clean_chunk}
    
    params = {}
    if voice and voice.strip():
        params["model"] = voice.strip()
    if encoding and encoding.strip():
        params["encoding"] = encoding.strip()
    
    # Only add sample_rate for encodings that support it
    if sample_rate and encoding and encoding.lower() not in ["mp3", "aac", "opus"]:
        params["sample_rate"] = sample_rate
    
    # Only add bit_rate for encodings that support it
    if bit_rate and encoding and encoding.lower() in ["mp3", "aac", "opus"]:
        if encoding.lower() == "mp3":
            if bit_rate not in [32000, 48000]:
                bit_rate = 48000
        params["bit_rate"] = bit_rate
    
    # Adjust speed for more natural pacing
    if speed is not None:
        # Slightly slow down if speed is too fast for natural speech
        adjusted_speed = min(speed, 1.2) if speed > 1.2 else speed
        params["speed"] = adjusted_speed
    else:
        params["speed"] = 0.95  # Slightly slower than default for more natural speech
    
    if pitch is not None:
        params["pitch"] = pitch
    if language:
        params["language"] = language
    if punctuate is not None:
        params["punctuate"] = str(punctuate).lower()
    if utterance_end_ms is not None:
        # Increase pause time for better pacing
        enhanced_pause = max(utterance_end_ms, 800)
        params["utterance_end_ms"] = enhanced_pause
    else:
        params["utterance_end_ms"] = 1200  # Default longer pause
    # Enhanced filler words configuration for more natural speech
    if filler_words is not None and filler_words:
        params["filler_words"] = "true"
        # Add additional parameters for more natural speech patterns
        params["disfluencies"] = "true"  # Enable speech disfluencies
        params["hesitations"] = "true"   # Enable hesitations like "um", "uh"
    elif filler_words is False:
        params["filler_words"] = "false"
        params["disfluencies"] = "false"
        params["hesitations"] = "false"
    
    if smart_format is not None:
        params["smart_format"] = str(smart_format).lower()
    if callback_url:
        params["callback_url"] = callback_url
    if callback_method:
        params["callback_method"] = callback_method.lower()
    
    # Add throttling delay before API call
    await asyncio.sleep(0.3)  # 300ms delay between chunks
    
    async with httpx.AsyncClient(timeout=45.0) as client:  # Increased timeout
        response = await client.post(DEEPGRAM_TTS_URL, headers=headers, json=payload, params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logging.error(f"Deepgram API error for chunk: {exc.response.status_code} - {exc.response.text}")
            raise HTTPException(status_code=502, detail=f"Deepgram API error: {exc.response.text}")
        
        # Add small delay after successful response
        await asyncio.sleep(0.2)
        return response.content

@app.post("/tts")
async def tts(
    req: TTSRequest,
    x_voice_token: str = Header(..., alias="x-voice-token")
):
    if x_voice_token != VOICE_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Chunk the text if it's too long
    text_chunks = chunk_text(req.text)
    
    if req.mode == "stream":
        async def audio_stream():
            for i, chunk in enumerate(text_chunks):
                logging.info(f"Processing chunk {i+1}/{len(text_chunks)}: {chunk[:50]}...")
                audio_bytes = await fetch_tts_audio_chunk(
                    chunk, 
                    req.voice, 
                    req.encoding,
                    req.sample_rate,
                    req.bit_rate,
                    req.speed,
                    req.pitch,
                    req.language,
                    req.punctuate,
                    req.utterance_end_ms,
                    req.filler_words,
                    req.smart_format,
                    req.callback_url,
                    req.callback_method
                )
                yield audio_bytes
                # Add inter-chunk delay for streaming
                if i < len(text_chunks) - 1:  # Don't delay after last chunk
                    await asyncio.sleep(0.5)
        
        return StreamingResponse(audio_stream(), media_type="audio/mpeg")
    else:
        # For file mode, process chunks with throttling
        audio_chunks = []
        for i, chunk in enumerate(text_chunks):
            logging.info(f"Processing file chunk {i+1}/{len(text_chunks)}: {chunk[:50]}...")
            audio_bytes = await fetch_tts_audio_chunk(
                chunk, 
                req.voice, 
                req.encoding,
                req.sample_rate,
                req.bit_rate,
                req.speed,
                req.pitch,
                req.language,
                req.punctuate,
                req.utterance_end_ms,
                req.filler_words,
                req.smart_format,
                req.callback_url,
                req.callback_method
            )
            audio_chunks.append(audio_bytes)
        
        # Create a zip file containing all audio chunks
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            for i, audio_chunk in enumerate(audio_chunks):
                zip_file.writestr(f"speech_part_{i+1:02d}.{req.encoding}", audio_chunk)
        
        zip_buffer.seek(0)
        return StreamingResponse(
            BytesIO(zip_buffer.getvalue()), 
            media_type="application/zip", 
            headers={"Content-Disposition": "attachment; filename=speech_chunks.zip"}
        )