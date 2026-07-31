# Sinhala Historical KG — Relation Extraction Pipeline

Fallback pipeline for Sinhala historical knowledge graph construction while
SinLLaMA / Aya-Expanse-8B (Module 3) is not yet accurate enough.

---

## Project Structure

```
sinhala_kg_pipeline/
├── .env.example                  ← copy to .env and fill API key
├── requirements.txt
├── normalizer.py                 ← entity alias + relation surface-form normalization
├── ner_pipeline.py               ← XLM-RoBERTa NER model loader & inference
├── deepseek_relation_extractor.py← DeepSeek API call, prompt, parse, validate
├── pipeline.py                   ← main entry point (CLI + library)
├── tests/
│   ├── test_normalizer.py
│   └── test_pipeline_integration.py
└── models/
    └── xlmr_ner/                 ← place your trained NER model here
        ├── config.json
        ├── pytorch_model.bin
        ├── tokenizer_config.json
        └── tokenizer.json
```

---

## Setup

```bash
# 1. Clone / copy project
cd sinhala_kg_pipeline

.\venv\Scripts\streamlit.exe run app.py

```
