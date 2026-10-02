# Hindi → Telugu AI Video Dubbing

A production-grade, deployable application that takes Hindi videos and replaces the Hindi speech with naturally articulated Telugu speech, while preserving 100% of the original video visuals, frame rate, resolution, timing, and ambient background audio (music, sound effects, room tone).

---

## Architecture Overview

```text
┌─────────────────────────┐
│     Uploaded Video      │
└────────────┬────────────┘
             │
             ├── Video Stream ────────────────────────────────────────┐ (No Re-encoding: Stream Copy)
             │                                                        │
             └── Original Audio Track                                 │
                     │                                                │
                     ├──────────────┬──────────────────┐              │
                     │              │                  │              │
                     ▼              ▼                  ▼              │
                 16kHz Mono    48kHz Stereo      Silence & VAD        │
                     │              │                  │              │
               Faster-Whisper       │                  │              │
               (Speech-to-Text)     │                  │              │
                     │              │                  │              │
          Timestamped Hindi Segments│                  │              │
                     │              │                  │              │
           Neural Translation       │                  │              │
             (Hindi → Telugu)       │                  │              │
                     │              │                  │              │
          Translated Telugu Text    │                  │              │
                     │              │                  │              │
           Edge-TTS Neural Voice    │                  │              │
          (Mohan / Shruti Voices)   │                  │              │
                     │              │                  │              │
         Audio Time-Stretching      │                  │              │
         (Librubberband / Atempos)  │                  │              │
                     │              │                  │              │
         Synchronized Telugu Audio  │                  │              │
                     │              │                  │              │
                     └──────────────┼──────────────────┘              │
                                    ▼                                 │
                        FFmpeg Sidechain Ducking                      │
                        & EBU R128 Loudness Normalization             │
                                    │                                 │
                         Master Mixed Audio Track ────────────────────┤
                                                                      ▼
                                                       FFmpeg Stream Muxer (-c:v copy)
                                                                      │
                                                                      ▼
                                                          Final Telugu Dubbed Video
```

---

## Key Features

1. **Visual Fidelity Preservation**: Original video frames are never re-encoded or altered (`-c:v copy`), preserving resolution, aspect ratio, frame rate, and color grade.
2. **Timestamp-Aware Synchronization**: Individual speech segments are detected with exact start and end timestamps. The translated Telugu speech is matched to the interval using intelligent multi-pass rate adjustment and pitch-preserving time-stretching (`librubberband`).
3. **Studio-Quality Telugu Voices**: Employs Microsoft Azure neural voices (`te-IN-MohanNeural` Male, `te-IN-ShrutiNeural` Female) via Edge-TTS and fallback engines.
4. **Intelligent Background Ducking**: Background music and sound effects are retained; when Telugu speech is active, background audio dynamically ducks by a configurable depth (e.g. -12dB) with smooth attack/release transitions.
5. **Modern Material 3 Flutter UI**: Responsive frontend with drag-and-drop video upload, live pipeline progress tracking, side-by-side Before/After preview player, timestamped segment breakdown table, and direct download.
6. **Production-Ready & Fully Tested**: FastAPI backend with SQLite job persistence, complete pytest suite (9 tests passing), and Flutter widget test suite.

---

## Prerequisites

Before running the project locally, ensure you have:

- **Python**: Version 3.10 to 3.14 (`python --version`)
- **FFmpeg & FFprobe**: Version 5.0+ installed with `librubberband` on your system PATH (`ffmpeg -version`)
- **Flutter SDK**: Version 3.19+ with Dart 3.3+ (`flutter --version`)
- **Git**

---

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/morasantosh2007-rgb/video_dubbing.git
cd video_dubbing
```

### 2. Backend Setup
```bash
cd backend

# Create virtual environment (recommended)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Frontend Setup
```bash
cd ../frontend

# Install Flutter packages
flutter pub get
```

---

## Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

### Environment Variables Explained

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Backend bind host address |
| `PORT` | `8000` | Backend port |
| `ASR_PROVIDER` | `faster_whisper` | Speech recognition engine (`faster_whisper`, `groq`, `openai`, `google`) |
| `WHISPER_MODEL_SIZE` | `base` | Whisper model size (`tiny`, `base`, `small`, `medium`) |
| `TRANSLATION_PROVIDER` | `mymemory` | Translation engine (`mymemory`, `google`, `gemini`, `openai`, `groq`) |
| `TTS_PROVIDER` | `edge-tts` | Text-to-Speech provider (`edge-tts`, `gtts`) |
| `DEFAULT_TELUGU_VOICE` | `te-IN-MohanNeural` | Default male voice (`te-IN-MohanNeural`) |
| `DEFAULT_FEMALE_VOICE` | `te-IN-ShrutiNeural` | Default female voice (`te-IN-ShrutiNeural`) |
| `PRESERVE_BACKGROUND_AUDIO` | `true` | Retain background music and sound effects |
| `BACKGROUND_DUCKING_DB` | `-12.0` | Attenuation depth in decibels during dialogue |
| `MAX_UPLOAD_SIZE_MB` | `500` | Maximum video upload size in Megabytes |
| `GROQ_API_KEY` | *(optional)* | API key if `ASR_PROVIDER=groq` or `TRANSLATION_PROVIDER=groq` |
| `OPENAI_API_KEY` | *(optional)* | API key if `ASR_PROVIDER=openai` or `TRANSLATION_PROVIDER=openai` |
| `GEMINI_API_KEY` | *(optional)* | API key if `TRANSLATION_PROVIDER=gemini` |

---

## Running the Application Locally

### Step 1: Start the Backend
From the project root:
```bash
cd backend
python run.py
```
The FastAPI backend will start at `http://127.0.0.1:8000`.
- API Health check: `http://127.0.0.1:8000/api/health`
- Interactive Swagger API docs: `http://127.0.0.1:8000/docs`

### Step 2: Start the Flutter Frontend
In a new terminal window:
```bash
cd frontend

# Run in Chrome:
flutter run -d chrome

# Or run as Windows desktop app:
flutter run -d windows
```

---

## Running Automated Tests

### Backend Tests (9 passing tests)
```bash
cd backend
python -m pytest tests/ -v
```
Tests include:
- `test_api.py`: Health, languages, voices, job retrieval
- `test_services.py`: Neural translation, Edge-TTS audio generation, FFmpeg audio stretching
- `test_pipeline_e2e.py`: Full end-to-end dubbing pipeline with real speech generation, video creation, transcription, translation, TTS, audio synchronization, ducking, and video muxing

### Frontend Tests (3 passing tests)
```bash
cd frontend
flutter analyze
flutter test
```

---

## Docker Deployment

To build and run the entire backend container with FFmpeg and Python dependencies:

```bash
docker compose up --build -d
```

View live logs:
```bash
docker compose logs -f
```

---

## REST API Specification

- `POST /api/jobs`: Upload a Hindi video and initiate background dubbing
- `GET /api/jobs/{job_id}`: Retrieve job details and progress
- `GET /api/jobs/{job_id}/progress`: Lightweight polling endpoint for progress updates
- `GET /api/jobs/{job_id}/segments`: Retrieve timestamped speech segments (Hindi vs Telugu)
- `GET /api/jobs/{job_id}/video/original`: Stream original video file
- `GET /api/jobs/{job_id}/video/dubbed`: Stream final Telugu dubbed video
- `GET /api/jobs/{job_id}/download`: Download final dubbed MP4 file
- `DELETE /api/jobs/{job_id}`: Cancel/delete job and associated files
- `GET /api/voices`: List supported TTS voices
- `GET /api/languages`: List supported languages
- `GET /api/health`: Health status check
