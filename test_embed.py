import os
from dotenv import load_dotenv
load_dotenv('clario-ml-sidecar/.env')
from google import genai
from google.genai import types

client = genai.Client()
res = client.models.embed_content(
    model="gemini-embedding-2",
    contents=["hello", "world"],
    config=types.EmbedContentConfig(output_dimensionality=384)
)
print(len(res.embeddings))
