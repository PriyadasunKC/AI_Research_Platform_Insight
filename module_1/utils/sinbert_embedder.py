# sinbert_embedder.py
# Uses SinBERT to convert Sinhala essays into embeddings

import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel

class SinBERTEmbedder:
    """
    Loads SinBERT and converts Sinhala text
    into numerical embeddings (vectors).
    
    These embeddings capture the MEANING of 
    the Sinhala text much better than 
    simple word counting.
    """

    MODEL_NAME = "NLPC-UOM/SinBERT-large"

    def __init__(self):
        print("\n Loading SinBERT model...")
        print(f" Model: {self.MODEL_NAME}")
        print(" (First run will download ~300MB — please wait)\n")

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.MODEL_NAME
        )
        self.model = AutoModel.from_pretrained(
            self.MODEL_NAME
        )
        self.model.eval()
        print(" ✓ SinBERT loaded successfully!\n")

    def get_embedding(self, text):
        """
        Convert a Sinhala text into a 
        fixed size embedding vector.
        
        Uses [CLS] token representation
        which captures overall text meaning.
        """
        # Tokenize
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            max_length=512,
            truncation=True,
            padding=True
        )

        # Get embeddings (no gradient needed)
        with torch.no_grad():
            outputs = self.model(**inputs)

        # Use [CLS] token = overall text meaning
        cls_embedding = outputs.last_hidden_state[:, 0, :]
        return cls_embedding.squeeze().numpy()

    def get_embeddings_batch(self, texts):
        """
        Get embeddings for multiple texts at once.
        Returns a 2D array (num_texts x embedding_size)
        """
        embeddings = []
        for i, text in enumerate(texts):
            print(f" Embedding essay {i+1}/{len(texts)}...",
                  end="\r")
            emb = self.get_embedding(text)
            embeddings.append(emb)
        print(" ✓ All embeddings generated!          ")
        return np.array(embeddings)


# ── Test it ──────────────────────────────────────────────
if __name__ == "__main__":
    embedder = SinBERTEmbedder()

    test_texts = [
        "දේවානම්පියතිස්ස රජතුමා ක්‍රි.පූ. 247 සිට රාජ්‍ය කළේය.",
        "මහාවංශය ශ්‍රී ලංකාවේ ප්‍රධාන ඓතිහාසික මූලාශ්‍රයකි."
    ]

    for i, text in enumerate(test_texts):
        emb = embedder.get_embedding(text)
        print(f"\n Essay {i+1}:")
        print(f"  Text      : {text[:50]}...")
        print(f"  Embedding : shape={emb.shape}, "
              f"first 5 values={emb[:5].round(3)}")