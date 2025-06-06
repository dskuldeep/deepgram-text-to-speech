<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

- This project is a FastAPI-based Python API for text-to-speech using Deepgram.
- The /tts endpoint requires authentication via the x-voice-token header.
- The endpoint supports both audio file download and streaming modes, selectable via the 'mode' field in the request body.
- Use async httpx for low-latency Deepgram API calls.
