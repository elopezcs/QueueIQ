# QueueIQ ArrivalSignal

ArrivalSignal is the pre-arrival demand shaping module for QueueIQ.

## Preferred local run

Use the shared root `.venv` from the repository root. Module-specific virtual environments are no longer part of the supported setup.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd Chatbot\frontend
npm install
cd ..\..
.\.venv\Scripts\python.exe app.py
```

That launcher starts both:
- Chatbot backend on `http://127.0.0.1:8000/docs`
- Chatbot frontend on `http://127.0.0.1:5173`

## Manual Chatbot-only run

Backend:

```powershell
cd Chatbot\backend
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd Chatbot\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

## Appointment Confirmation Previews

Each successful frontend Book Now booking (`POST /appointments`) generates a local HTML confirmation artifact for that appointment.

- Scope: local demo/validation artifact only (no SMTP/email delivery)
- Output folder: `Chatbot/backend/reports/email_previews/bookings/`
- Filename pattern: `appointment_confirmation_<appointment_id>.html`
- Confirmation number format in the HTML: 6-character uppercase alphanumeric (`A-Z`, `0-9`)

Quick local verification:
1. Start QueueIQ and complete a booking in the Chatbot frontend using Book Now.
2. Open `Chatbot/backend/reports/email_previews/bookings/`.
3. Confirm a new `appointment_confirmation_<appointment_id>.html` file was created.
4. Open the file in a browser and verify the appointment details and confirmation number are present.

Optional email-send environment variables:

- `QUEUEIQ_EMAIL_ENABLED`: set to `true` to allow SMTP send attempts for appointment confirmation emails
- `QUEUEIQ_EMAIL_SENDER`: sender email account used for SMTP auth (Gmail account)
- `QUEUEIQ_EMAIL_APP_PASSWORD`: app password for the sender account

Example:

```env
QUEUEIQ_EMAIL_ENABLED=false
QUEUEIQ_EMAIL_SENDER=your_email@gmail.com
QUEUEIQ_EMAIL_APP_PASSWORD=your_app_password
```

## Notes

- The backend runs in stub mode if `OPENAI_API_KEY` is not set.
- The backend allows both `http://localhost:5173` and `http://127.0.0.1:5173` for local frontend access.
- Use the root `requirements.txt` as the shared dependency file for the full workspace.

## Assistant TTS Providers

Assistant voice output is opt-in and disabled by default.

- `VOICE_OUTPUT_ENABLED=false` keeps the app behavior unchanged.
- `VOICE_OUTPUT_ENABLED=true` and `VOICE_OUTPUT_PROVIDER=system` uses the existing browser/system narrator speech path in the frontend.
- `VOICE_OUTPUT_ENABLED=true` and `VOICE_OUTPUT_PROVIDER=openai` sends assistant text to backend `POST /rag/chat/tts`, then plays returned audio in the frontend.

Backend OpenAI TTS settings:

```env
VOICE_OUTPUT_ENABLED=true
VOICE_OUTPUT_PROVIDER=openai
OPENAI_API_KEY=your_openai_key
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_VOICE=coral
OPENAI_TTS_INSTRUCTIONS=
OPENAI_TTS_AUDIO_FORMAT=mp3
OPENAI_TTS_SPEED=1.0
```

`OPENAI_TTS_SPEED` controls speaking rate for OpenAI-generated audio (clamped to `0.25`-`4.0`, default `1.0`).

If OpenAI voice playback sounds like it ramps up at the very start on a specific browser/device, test `OPENAI_TTS_AUDIO_FORMAT=wav` to compare behavior against MP3 decoding.
If this only occurs on specific Windows machines, also test with OS/device audio enhancements disabled before changing app logic further.

Safety and fallback behavior:

- `OPENAI_API_KEY` remains backend-only; no frontend key exposure.
- Invalid or missing `VOICE_OUTPUT_PROVIDER` safely falls back to `system`.
- If OpenAI TTS fails, chat text rendering and typed chat continue working.
