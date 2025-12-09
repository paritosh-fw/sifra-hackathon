# 🤖 Sifra - AI-Powered Support Ticket Analysis

**Hackathon Project** - Freshworks Hackathon 2025

## 🎯 What is Sifra?

Sifra is an AI-powered support ticket analysis system that automates root cause investigation by:

- 📋 Reading Freshdesk support tickets
- 🔍 Searching Haystack production logs
- 🧠 Using Claude LLM for intelligent analysis
- 💬 Responding via Slack with actionable insights

## 🚀 Features

| Feature | Description |
|---------|-------------|
| **Slack Bot** | Listens for ticket URLs, responds with analysis |
| **Freshdesk Integration** | Reads ticket details, conversations |
| **Haystack Log Search** | Searches production logs for errors |
| **AI Root Cause Analysis** | Claude-powered diagnosis & recommendations |

## 📊 Demo Flow

```
User posts ticket URL in Slack
         ↓
    Sifra reads Freshdesk ticket
         ↓
    Extracts UUIDs/Account IDs
         ↓
    Searches Haystack logs
         ↓
    Claude analyzes everything
         ↓
    Posts root cause analysis to Slack
```

## 🛠️ Tech Stack

- **Python 3.11+**
- **Claude LLM** (via Cloudverse)
- **LangChain** - LLM orchestration
- **Slack SDK** - Bot integration
- **Freshdesk API** - Ticket reading
- **Haystack** - Log search

## ⚡ Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run Slack bot (listens for ticket URLs)
python run.py

# Or analyze a single ticket
python run.py "https://support.freshdesk.com/a/tickets/12345"
```

## 📁 Project Structure

```
sifra-hackathon/
├── config.yaml         # Configuration (API keys, tokens)
├── requirements.txt    # Python dependencies
├── run.py             # Entry point
└── sifra/
    ├── __init__.py
    ├── agents/        # AI agents
    ├── tools/         # Integration tools
    ├── utils/         # Utilities & config
    ├── crew.py        # CrewAI orchestration
    └── main.py        # Main logic
```

## 👨‍💻 Author

**Paritosh Agarwal** - Staff Engineer, Freshworks

## 📈 Impact

- Reduces ticket investigation time by **~80%**
- Auto-correlates tickets with **2,000+ log entries**
- Provides instant root cause recommendations

---

*Built with ❤️ for Freshworks Hackathon 2025*

