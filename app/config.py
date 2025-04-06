import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    QUIZ_API_KEY = os.getenv("QUIZ_API_KEY")
    QUIZ_API_URL = os.getenv("QUIZ_API_URL")
    
settings = Settings()