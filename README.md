# IDD Care Bot

A simple web app to ask questions about research papers using AI.

## 🚀 Quick Start

### 1. Install Requirements
```bash
pip install -r requirements.txt
```

### 2. Setup Ollama (Local AI)
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Download a model
ollama pull mistral

# Start Ollama (keep this running)
ollama serve
```

### 3. Add Your Research Papers
Place CSV files in the `data/` folder with columns: `Title`, `Authors`, `Abstract`

Example `data/papers.csv`:
```csv
Title,Authors,Abstract
"Machine Learning in Healthcare","John Smith","This paper explores..."
```

### 4. Build Search Index
```bash
python idd_care_bot/ingest.py
```

### 5. Run the App
```bash
reflex run
```

### 6. Open Your Browser
Go to: http://localhost:3000

## 📁 What You Get

- **Frontend**: http://localhost:3000 (Web interface)
- **Backend**: http://localhost:8000 (API)

## ⚙️ Configuration

Create `.env` file (optional):
```env
OLLAMA_MODEL=mistral
EMBEDDING_MODEL=sentence-transformers/multi-qa-mpnet-base-dot-v1
```

## 🔧 Troubleshooting

**Ollama not working?**
```bash
# Check if Ollama is running
ollama list

# Restart Ollama
ollama serve
```

**Port already in use?**
```bash
# Stop processes on ports 3000/8000
pkill -f "reflex run"
```

## 🚀 Production
```bash
reflex run --env prod
```

## 📦 What's Included

- Semantic search for research papers
- Q&A with AI about paper content
- Local AI processing (no API keys needed)
- Simple web interface

## ❓ Need Help?

1. Check Ollama is running: `ollama list`
2. Ensure CSV files are in `data/` folder
3. Run `python idd_care_bot/ingest.py` after adding new papers

That's it! Your research paper search engine is ready. 🎉
