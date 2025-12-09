# 🤖 Sifra - AI-Powered Support Ticket Analysis

**Freshworks Hackathon 2025** | Dec 8-10, 2025

## 🎯 What is Sifra?

Sifra is an intelligent support ticket analysis system powered by **multi-agent AI architecture**. It automates root cause investigation by combining:

- 📋 **Ticket Analysis** - Reads Freshdesk support tickets
- 🔍 **Log Correlation** - Searches Haystack production logs & HAR files
- 🧠 **Code Analysis** - Investigates codebase to find root causes
- 📚 **Knowledge Base** - RAG-powered search over Confluence docs
- 💬 **Slack Integration** - Interactive bot with thread replies
- 🔧 **Fix Suggestions** - Provides actionable code fixes

## 🚀 Key Features

| Feature | Description |
|---------|-------------|
| **Multi-Agent System** | 8 specialized AI agents working together via CrewAI |
| **Semantic Code Search** | RAG-powered code search using ChromaDB embeddings |
| **HAR File Analysis** | Parse HAR files to extract UUIDs and correlate with logs |
| **@Sifra Code Queries** | Ask code questions directly via Slack mentions |
| **Confluence RAG** | Search internal knowledge base for solutions |
| **Account Detection** | Auto-detect account info from FreshOps |

## 🤖 AI Agents

```
┌─────────────────────────────────────────────────────────────┐
│                      Query Router                           │
│            (Routes to Ticket Analysis or Code Query)        │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
┌───────────────┐           ┌───────────────┐
│ Query Picker  │           │ Code Assistant│
│   (Tickets)   │           │  (@sifra)     │
└───────┬───────┘           └───────────────┘
        ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ Ticket Reader │────▶│ Log Analyzer  │────▶│ Code Analyzer │
└───────────────┘     └───────────────┘     └───────────────┘
                                                    │
                                                    ▼
                                            ┌───────────────┐
                                            │Slack Responder│
                                            └───────────────┘
```

## 📊 Workflow

### Ticket Analysis Flow
```
1. User posts Freshdesk ticket URL in #sifra-hackathon
2. Sifra reads ticket details and conversations
3. Extracts Haystack URLs or parses HAR files
4. Searches production logs for errors
5. Analyzes codebase for root cause
6. Posts analysis with fix suggestions as thread reply
```

### Code Query Flow
```
1. User mentions @Sifra with a code question
2. Sifra performs semantic search over codebase
3. Reads relevant files and analyzes code
4. Responds with detailed explanation
```

## 🛠️ Tech Stack

| Technology | Purpose |
|------------|---------|
| **CrewAI** | Multi-agent orchestration |
| **Claude LLM** | AI reasoning (via Cloudverse) |
| **ChromaDB** | Vector store for RAG |
| **Sentence Transformers** | Code embeddings |
| **Slack SDK** | Bot integration |
| **Freshdesk API** | Ticket reading |
| **Haystack** | Production log search |

## ⚡ Quick Start

```bash
# Clone the repository
git clone https://github.com/paritosh-fw/sifra-hackathon.git
cd sifra-hackathon

# Install dependencies
pip install -r requirements.txt

# Copy config template and add your credentials
cp config.yaml.example config.yaml
# Edit config.yaml with your API keys

# Run Sifra (listens for Slack messages)
python run.py

# Or analyze a single ticket
python run.py "https://support.freshdesk.com/a/tickets/12345"
```

## 📁 Project Structure

```
sifra-hackathon/
├── config.yaml.example    # Config template (copy to config.yaml)
├── requirements.txt       # Python dependencies
├── run.py                 # Entry point
├── data/
│   ├── har/               # HAR files for analysis
│   ├── code_vectors/      # Code embeddings (ChromaDB)
│   └── confluence_vectors/# Confluence embeddings
└── sifra/
    ├── agents/            # AI Agents
    │   ├── query_picker.py
    │   ├── query_router_agent.py
    │   ├── support_ticket_reader.py
    │   ├── log_url_generator.py
    │   ├── code_analysis_agent.py
    │   ├── code_assistant_agent.py
    │   └── slack_responder.py
    ├── tools/             # Integration Tools
    │   ├── freshdesk_tool.py
    │   ├── haystack_search_tool.py
    │   ├── har_parser_tool.py
    │   ├── semantic_code_search_tool.py
    │   ├── confluence_tool.py
    │   └── slack_tool.py
    ├── utils/             # Utilities
    │   ├── config.py
    │   ├── llm_config.py
    │   ├── code_rag.py
    │   └── confluence_rag.py
    ├── crew.py            # CrewAI orchestration
    └── main.py
```

## 💬 Slack Commands

| Command | Description |
|---------|-------------|
| `https://support.freshdesk.com/a/tickets/123` | Analyze a Freshdesk ticket |
| `@Sifra how does authentication work?` | Ask a code question |
| `@Sifra where is TicketService defined?` | Find code definitions |

## 📈 Impact

- ⏱️ Reduces ticket investigation time by **~80%**
- 🔗 Auto-correlates tickets with production logs
- 💡 Provides instant root cause analysis
- 🔧 Suggests specific code fixes
- 📚 Leverages internal knowledge base

## 👨‍💻 Author

**Paritosh Agarwal** - Staff Engineer, Freshworks

---

*Built with ❤️ for Freshworks Hackathon 2025*
