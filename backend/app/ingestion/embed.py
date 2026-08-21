import os
import httpx
import hashlib
import numpy as np

def get_embedding(text: str) -> list[float]:
    # Primary: OpenAI text-embedding-3-small (1536 dimensions)
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            headers = {
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "input": text,
                "model": "text-embedding-3-small"
            }
            res = httpx.post("https://api.openai.com/v1/embeddings", headers=headers, json=payload, timeout=15.0)
            if res.status_code == 200:
                data = res.json()
                return data["data"][0]["embedding"]
            else:
                print(f"OpenAI embedding API returned status {res.status_code}: {res.text}")
        except Exception as e:
            print(f"OpenAI embedding exception: {e}")

    # Alternative: Voyage AI voyage-3. Note voyage-3 output size is 1024.
    # To keep DB schema consistent with 1536 vector length, we'll pad the Voyage vector if it is activated.
    voyage_key = os.getenv("VOYAGE_API_KEY")
    if voyage_key:
        try:
            headers = {
                "Authorization": f"Bearer {voyage_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "input": [text],
                "model": "voyage-3"
            }
            res = httpx.post("https://api.voyageai.com/v1/embeddings", headers=headers, json=payload, timeout=15.0)
            if res.status_code == 200:
                data = res.json()
                embedding = data["data"][0]["embedding"]  # 1024 dim
                # Pad to 1536 dim
                padded = embedding + [0.0] * (1536 - len(embedding))
                return padded
            else:
                print(f"Voyage embedding API returned status {res.status_code}: {res.text}")
        except Exception as e:
            print(f"Voyage embedding exception: {e}")

    # Fallback: Deterministic pseudo-random unit vector
    print("Warning: No active embedding API keys found. Using pseudo-random fallback vector.")
    seed_hash = int(hashlib.md5(text.encode('utf-8')).hexdigest(), 16) % (2**32)
    np.random.seed(seed_hash)
    vec = np.random.randn(1536)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()
