"""
Wake word detection engine for JARVIS.

Features:
- Always-on offline wake-word detection using openWakeWord.
- Detects "Hey Jarvis".
- F8 provides instant manual activation.
- Optional Google STT fallback for low-confidence detections.
- Emits event-bus states for HUD integration.
"""

import time
import threading

import numpy as np
from openwakeword.model import Model
from pvrecorder import PvRecorder

from core.event_bus import event_bus


# ---------------------------------------------------------------------------
# Optional Windows keyboard support
# ---------------------------------------------------------------------------

try:
    import win32api

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


# ---------------------------------------------------------------------------
# Optional speech-recognition fallback
# ---------------------------------------------------------------------------

try:
    import speech_recognition as sr

    _sr_recognizer = sr.Recognizer()
    _sr_recognizer.energy_threshold = 80
    _sr_recognizer.dynamic_energy_threshold = True
    _sr_recognizer.pause_threshold = 0.4
    HAS_SR = True
except ImportError:
    HAS_SR = False


# ---------------------------------------------------------------------------
# Wake-word configuration
# ---------------------------------------------------------------------------

WAKE_WORD = "hey_jarvis"

# Keep the proven threshold from the original working implementation.
WAKE_THRESHOLD = 0.35

# Low-confidence range where STT can optionally confirm the phrase.
FUZZY_MIN = 0.03
FUZZY_MAX = 0.35

# Prevent repeated Google STT requests.
_last_fuzzy_time = 0.0
_FUZZY_COOLDOWN = 1.5


# Phrases accepted by the optional STT fallback.
WAKE_PHRASES = (
    "hey jarvis",
    "jarvis",
)


# ---------------------------------------------------------------------------
# openWakeWord model
# ---------------------------------------------------------------------------

oww_model = Model(
    wakeword_models=[WAKE_WORD],
    inference_framework="onnx",
)


# ---------------------------------------------------------------------------
# STT fallback
# ---------------------------------------------------------------------------

def _check_phrase_via_stt(audio_chunk_int16: np.ndarray) -> bool:
    """
    Check a short audio buffer using speech recognition.

    This is only used when openWakeWord detects a low-confidence signal.
    It is a fallback, not the primary wake-word detector.
    """

    global _last_fuzzy_time

    if not HAS_SR:
        return False

    now = time.time()

    if now - _last_fuzzy_time < _FUZZY_COOLDOWN:
        return False

    _last_fuzzy_time = now

    try:
        raw_bytes = audio_chunk_int16.tobytes()

        audio_data = sr.AudioData(
            raw_bytes,
            sample_rate=16000,
            sample_width=2,
        )

        text = _sr_recognizer.recognize_google(
            audio_data,
            language="en-IN",
        ).lower()

        print(f"[STT fallback] Heard: '{text}'")

        return any(phrase in text for phrase in WAKE_PHRASES)

    except Exception:
        return False


# ---------------------------------------------------------------------------
# Wake-word listener
# ---------------------------------------------------------------------------

def wait_for_wake_word():
    """
    Block until JARVIS detects the wake word or F8 is pressed.

    Detection priority:

    1. F8 manual activation.
    2. openWakeWord confident detection.
    3. Optional STT confirmation for low-confidence audio.
    """

    # Give the audio system a moment to initialize.
    time.sleep(0.5)

    # Reset the model so stale prediction state does not carry over.
    try:
        oww_model.reset()
    except Exception:
        pass

    # -----------------------------------------------------------------------
    # Start microphone
    # -----------------------------------------------------------------------

    try:
        recorder = PvRecorder(
            device_index=0,
            frame_length=1280,
        )

        recorder.start()

    except Exception as e:
        print(f"[WAKE] Failed to start microphone: {e}")
        time.sleep(0.5)
        return

    print("Waiting for wake word... (say 'Hey Jarvis')")

    try:
        event_bus.emit_state(
            "IDLE",
            "Waiting for 'Hey Jarvis'",
        )
    except Exception:
        pass

    # Rolling audio buffer.
    #
    # 12 frames × 1280 samples/frame ≈ 0.96 seconds
    # at a 16 kHz sample rate.
    audio_buffer = []
    max_buffer_frames = 12

    try:

        while True:

            # ----------------------------------------------------------------
            # Priority 1: F8 manual activation
            # ----------------------------------------------------------------

            if HAS_WIN32:

                try:

                    # VK_F8 = 0x77
                    if win32api.GetAsyncKeyState(0x77) & 0x8000:

                        try:
                            event_bus.emit_state(
                                "WAKE",
                                "Activated via F8",
                            )
                        except Exception:
                            pass

                        print("\n[WAKE] Activated via F8 key!")

                        return

                except Exception:
                    pass

            # ----------------------------------------------------------------
            # Read microphone frame
            # ----------------------------------------------------------------

            pcm = recorder.read()

            audio = np.array(
                pcm,
                dtype=np.int16,
            )

            # Maintain rolling buffer for STT fallback.
            audio_buffer.append(audio)

            if len(audio_buffer) > max_buffer_frames:
                audio_buffer.pop(0)

            # ----------------------------------------------------------------
            # Priority 2: openWakeWord
            # ----------------------------------------------------------------

            prediction = oww_model.predict(audio)

            score = prediction.get(
                WAKE_WORD,
                0.0,
            )

            # Simple terminal feedback.
            if score > 0.1:

                print(
                    f"Score: {score:.3f}",
                    end="\r",
                    flush=True,
                )

            # ----------------------------------------------------------------
            # Confident detection
            # ----------------------------------------------------------------

            if score >= WAKE_THRESHOLD:

                try:
                    event_bus.emit_state(
                        "WAKE",
                        "Wake word detected",
                    )
                except Exception:
                    pass

                print(
                    f"\n[WAKE] 'Hey Jarvis' detected! "
                    f"(Score: {score:.3f})"
                )

                return

            # ----------------------------------------------------------------
            # Low-confidence STT fallback
            # ----------------------------------------------------------------

            elif FUZZY_MIN <= score < FUZZY_MAX:

                if len(audio_buffer) >= 6:

                    combined = np.concatenate(
                        audio_buffer
                    )

                    if _check_phrase_via_stt(combined):

                        try:
                            event_bus.emit_state(
                                "WAKE",
                                "Wake phrase confirmed",
                            )
                        except Exception:
                            pass

                        print(
                            "\n[WAKE] 'Hey Jarvis' confirmed via voice!"
                        )

                        return

    finally:

        # --------------------------------------------------------------------
        # Always release microphone resources.
        # --------------------------------------------------------------------

        try:
            recorder.stop()
        except Exception:
            pass

        try:
            recorder.delete()
        except Exception:
            pass