import supabase
from sentence_transformers import SentenceTransformer
from app.config import settings
import torch

def get_supabase_client():
    return supabase.create_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_KEY
    )

def get_embedding_model():
    # Initialize model with explicit device setting
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = SentenceTransformer('BAAI/bge-small-zh-v1.5', device=device)
    return model