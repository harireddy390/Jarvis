import time
import numpy as np
from openwakeword.model import Model
from pvrecorder import PvRecorder

oww_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")


def wait_for_wake_word():
    """
    Blocks until the wake word "Hey Jarvis" is detected, then returns.
    """
    time.sleep(0.5)

    try:
        recorder = PvRecorder(device_index=0, frame_length=1280)
        recorder.start()
    except Exception as e:
        print(f"Failed to start microphone for wake word: {e}")
        time.sleep(1)
        return

    print("Waiting for wake word... (say 'Hey Jarvis')")

    try:
        while True:
            pcm = recorder.read()
            audio = np.array(pcm, dtype=np.int16)
            prediction = oww_model.predict(audio)
            score = prediction["hey_jarvis"]

            if score > 0.1:
                print(f"Score: {score:.3f}")

            if score > 0.35:
                print("Wake word detected!")
                break
    finally:
        recorder.stop()
        recorder.delete()