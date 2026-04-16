import os
from dotenv import load_dotenv
from typing import Optional

def load_api_key() -> Optional[str]:
    """
    Get the API key from the environmental variables
    """
    
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("You have not set a Groq API Key yet")
    return api_key
