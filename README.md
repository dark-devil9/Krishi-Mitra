# Agroculture

A context-aware agriculture assistant that provides market prices (Agmarknet), weather insights, proactive alerts, Hindi/English voice I/O, and a clean web UI.

## 1) Prerequisites
- Python 3.10 or 3.11 (recommended)
- pip installed
- Internet connectivity for APIs and model downloads

## 2) Installation
```bash
# From repository root
python -m venv .venv
# Windows PowerShell
. .venv\Scripts\Activate.ps1
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

Environment variables (create a .env file in repo root):
```
AGMARKNET_API_KEY=your_data_gov_in_api_key
MISTRAL_API_KEY=your_mistral_api_key
```

## 3) Build the local vector DB (RAG)
Run the RAG script once to build the local knowledge base used by the chatbot’s advisory logic.
```bash
python rag.py
```
This will populate/refresh the `agri_db/` directory.

## 4) Start the backend (FastAPI + Uvicorn)
```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
- API docs: `http://127.0.0.1:8000/docs`
- Useful endpoints:
  - `GET /status?user_id=<id>`
  - `GET /alerts?user_id=<id>`
  - `POST /alerts/run-now?user_id=<id>` (generate alerts immediately)
  - `POST /voice/transcribe` (ASR; defaults to Hindi)
  - `POST /voice/ask` (audio in → text + base64 MP3 out)
  - `POST /tts` (text → base64 MP3; auto en-IN/hi-IN)

## 5) Open the UI
Open `index.html` directly in your browser. It connects to the backend at `http://127.0.0.1:8000` by default.

Optionally serve it from a local static server:
```bash
# Python simple server (example)
python -m http.server 5173
# Open: http://127.0.0.1:5173/index.html
```

## 6) Typical workflow
1. Install dependencies: `pip install -r requirements.txt`
2. Create `.env` with your keys
3. Build RAG DB: `python rag.py`
4. Start backend: `uvicorn main:app --host 127.0.0.1 --port 8000 --reload`
5. Open `index.html` in your browser

## 7) Notes & Tips
- Voice input defaults to Hindi recognition to prevent Urdu autodetection. For English, pass `?lang=en` to `/voice/ask`.
- TTS uses Edge voices: `en-IN-NeerjaNeural` (English), `hi-IN-SwaraNeural` (Hindi).
- Alerts are generated hourly; use `POST /alerts/run-now?user_id=<id>` to generate on demand.
- If Whisper install has NumPy/Numba issues, faster-whisper is used automatically.
