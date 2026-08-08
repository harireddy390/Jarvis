import logging
import os

LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "jarvis.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("JARVIS")