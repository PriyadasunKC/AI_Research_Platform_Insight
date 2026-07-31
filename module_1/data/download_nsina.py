# download_nsina.py
# Downloads NSina Sinhala news corpus

from datasets import load_dataset 
import pandas as pd
import os

from dotenv import load_dotenv

load_dotenv() 

HF_TOKEN = os.environ.get("HF_TOKEN")
if not HF_TOKEN:
    raise ValueError("HF_TOKEN not found - check your .env file")


print("Downloading NSina corpus...")
dataset = load_dataset("sinhala-nlp/NSINA", split="train", token=HF_TOKEN)

df = pd.DataFrame(dataset)
print(f"Total articles: {len(df)}")
print(f"Columns: {df.columns.tolist()}")
print(f"\nSample article:\n{df['content'][0][:300]}")

# Save locally
df.to_csv("data/nsina_corpus.csv", index=False)
print("\n✓ Saved to data/nsina_corpus.csv")