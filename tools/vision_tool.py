import cv2
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def see_camera(question: str = "Describe what you see") -> str:
    """
    Captures a photo from the webcam and analyzes it with vision AI to answer
    a question about what's currently visible. Use this whenever the user asks
    what you can see, what's in front of them, or to look at/identify something
    via the camera, e.g. "what do you see", "what am I holding", "look at this".
    """
    cam = cv2.VideoCapture(0)
    ret, frame = cam.read()
    cam.release()

    if not ret:
        return "I couldn't access the camera right now."

    image_path = "captured_frame.jpg"
    cv2.imwrite(image_path, frame)

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    response = client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            question
        ]
    )

    os.remove(image_path)
    return response.text