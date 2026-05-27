# Wiki-LLM - V1
## An Agentic Knowledge Base Powered by LLMs

**Wiki-LLM** is an intelligent, self-maintaining knowledge base system that leverages Large Language Models (LLMs) to think, reason, and autonomously organize information into a structured wiki Based on the **Andrej Karpathy’s** "LLM Wiki". It combines agentic AI with document management, web search, and real-time interaction through a modern web interface.

---

## 🎯 Project Overview

Wiki-LLM transforms how you interact with and organize knowledge by:

- **Agentic Intelligence**: An AI agent that thinks through problems, decides what tools to use, and takes autonomous actions
- **Knowledge Management**: Automatically organize, synthesize, and maintain a living knowledge base in markdown format
- **Multi-Provider Support**: Works with Google Gemini (default), OpenAI, Anthropic, and HuggingFace models
- **Real-Time Interaction**: WebSocket-based streaming for live agent responses and tool execution
- **File Analysis**: Process raw documents (PDFs, TXT, DOCX, HTML, JSON, CSV, images) and extract structured knowledge
- **Web Integration**: Search the web in real-time and incorporate findings into your knowledge base
- **REST & WebSocket APIs**: Full-featured backend for programmatic access and real-time communication

---

## 📁 Project Structure

```
WiKi-LLM -V1/
├── agent_modular/           # Main modular agent implementation (RECOMMENDED)
│   ├── agent.py             # Core agentic loop with streaming
│   ├── server.py            # FastAPI backend server
│   ├── tools.py             # Tool implementations (wiki, file ops, search)
│   ├── config.py            # Configuration management
│   ├── tool_converter.py    # Provider-specific tool format conversion
│   ├── requirements.txt      # Python dependencies
│   └── providers/           # Multi-provider LLM support
│       ├── base.py          # Abstract provider interface
│       ├── gemini.py        # Google Gemini provider
│       ├── openai.py        # OpenAI GPT provider
│       └── huggingface.py   # HuggingFace model provider
│
├── agent/                    # Legacy agent implementation (for reference)
│   ├── agent.py
│   ├── server.py
│   └── tools.py
│
├── ui/                       # Web frontend
│   ├── index.html           # Main UI page with tabs and chat interface
│   ├── app.js               # JavaScript frontend logic
│   └── style.css            # Modern styling with gradients and animations
│
├── wiki/                     # Knowledge base (auto-maintained)
│   ├── index.md             # Knowledge base index
│   ├── Apache Kafka.md       # Example: Big data streaming
│   ├── Apache Spark.md       # Example: Distributed computing
│   ├── TradingAgents.md      # Example: Stock trading agents
│   ├── transformer_attention.md
│   ├── prompt_engineering_best_practices.md
│   └── [more markdown files...]
│
├── raw/                      # Raw document storage for analysis
│   ├── Module 5 IoT.txt
│   ├── TradingAgents.txt
│   └── [uploaded files...]
│
├── requirements.txt          # Root dependencies
├── start.bat                # Windows startup script
├── .env.example             # Template for environment variables
└── README.md                # This file
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+**
- **LLM API Key** (Google Gemini recommended for free tier):
  - [Get Gemini API Key](https://aistudio.google.com/apikey)
  - Or use OpenAI, Anthropic, HuggingFace APIs

### Installation & Setup

#### 1. **Windows Users** (Easiest)
```bash
# Simply run the batch file
start.bat
```
This will:
- Check for `.env` file and create from template if missing
- Prompt you to add your API key
- Install dependencies
- Start the server

#### 2. **Manual Setup** (All Platforms)
```bash
# Install dependencies
pip install -r agent_modular/requirements.txt

# Create .env file
cp .env.example .env

# Edit .env and add your API key
# GEMINI_API_KEY=your_key_here
# Or for other providers:
# OPENAI_API_KEY=your_key_here
# ANTHROPIC_API_KEY=your_key_here
# etc.

# Start the server
cd agent_modular
python server.py
```

### 3. **Access the Web Interface**
Open your browser and navigate to:
```
http://localhost:8000
```

You'll see:
- **Agent Tab**: Chat with the AI agent in real-time
- **Wiki Files Tab**: Browse and edit knowledge base files
- **Knowledge Base Tab**: View structured information with backlinks

---

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root with:

```ini
# LLM Provider Selection
LLM_PROVIDER=gemini          # Options: gemini, openai, anthropic, huggingface
LLM_MODEL=gemini-2.5-flash-lite  # Model name per provider

# API Keys (only set the one you're using)
GEMINI_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
HUGGINGFACE_API_KEY=your_key_here

# Agent Behavior
LLM_TEMPERATURE=0.1          # Lower = more deterministic, Higher = more creative
LLM_MAX_ITERATIONS=6         # Max steps for agent to take before stopping
```

### Provider-Specific Models

```python
# Gemini (Recommended - Free tier available)
gemini-2.5-flash-lite        # Fastest, good for reasoning
gemini-2.5-flash             # Balanced

# OpenAI
gpt-4-turbo                  # Most capable
gpt-4o                       # Latest

# Anthropic
claude-3-5-sonnet-20241022   # Latest Claude

# HuggingFace
microsoft/DialoGPT-medium    # Open-source dialogue model
```

---

## 🛠 Core Features & Tools

### 1. **Wiki Management Tools**
The agent can automatically manage your knowledge base:

- **`list_wiki_files()`** - List all markdown files in `/wiki`
- **`read_wiki_file(filename)`** - Read wiki file content
- **`write_wiki_file(filename, content)`** - Create or update wiki files
- **`delete_wiki_file(filename)`** - Remove wiki files

### 2. **Raw File Analysis**
Process and extract knowledge from raw documents:

- **`list_raw_files()`** - List all raw documents in `/raw`
- **`read_raw_file(filename)`** - Read content from raw files (supports: PDF, TXT, MD, DOCX, HTML, JSON, CSV, images)

### 3. **Web Search**
Real-time internet search integration:

- **`web_search(query)`** - Search the web using DuckDuckGo
- Results are returned as structured data for agent processing

### 4. **Code Execution** (Optional)
The agent can execute Python code for calculations and analysis.

---

## 🏗 Architecture

### Agent Loop Flow

```
User Input
    ↓
[Agent Thinking] ← Ask LLM for next action
    ↓
[Decision Tree]
    ├─→ Generate Answer → Stream to UI
    ├─→ Call Tool (Wiki, Web, File) → Execute → Add Result to Context
    ├─→ Process More → Loop (until max_iterations or final answer)
    └─→ No More Tools → Return Final Answer
    ↓
User Sees Streamed Response + Tool Calls
```

### Backend Architecture

**FastAPI Server** handles:
- `/ws` - WebSocket endpoint for real-time agent streaming
- `/api/wiki` - REST endpoints for wiki file management (GET, POST, DELETE)
- `/` - Static file serving for web UI
- CORS middleware for cross-origin requests

### Multi-Provider Support

The system uses an abstract `BaseProvider` interface:

```python
class BaseProvider:
    def initialize(config)      # Setup API credentials
    def send_message(...)       # Send message, handle tool calls
    def format_chat_history()   # Format messages per provider
```

Implementations:
- `gemini.py` - Google Generative AI API
- `openai.py` - OpenAI Chat Completion API
- `anthropic.py` - Anthropic Claude API
- `huggingface.py` - HuggingFace Models

---

## 📊 Use Cases

### 1. **Personal Knowledge Management**
- Automatically organize research into a structured wiki
- Create backlinks between related concepts
- Keep knowledge up-to-date with web search

### 2. **Research Automation**
- Analyze raw documents and extract key information
- Synthesize findings into comprehensive notes
- Generate summaries and comparisons

### 3. **Documentation Generation**
- Convert unstructured content into well-formatted markdown
- Create index pages with navigable structure
- Maintain consistency across documentation

### 4. **Learning & Education**
- Build course-specific knowledge bases
- Generate summaries of complex topics
- Create study guides with interconnected concepts

### 5. **Domain Expertise Building**
- Accumulate knowledge in specialized areas
- Create searchable reference materials
- Maintain up-to-date information with web search

---

## 🎨 Web Interface Features

### Chat Tab
- **Real-time streaming**: Watch the agent think and act
- **Tool visualization**: See what tools the agent uses
- **Conversation history**: Multi-turn context awareness
- **Status indicator**: Connection status and activity monitoring

### Wiki Files Tab
- **File browser**: List all wiki documents
- **Search**: Find files by name
- **Edit mode**: Create and modify markdown files
- **Delete**: Remove outdated documents

### Knowledge Base Tab
- **Structured view**: Navigate organized information
- **Backlinks**: See related documents
- **Cross-references**: Jump between connected topics
- **Full-text search**: Find information across the KB

---

## 🔐 Security Considerations

⚠️ **Important for Production**:

1. **API Key Management**:
   - Never commit `.env` files
   - Use environment variable secrets in production
   - Rotate keys regularly

2. **CORS Configuration**:
   - Update `allow_origins` in `server.py` for production
   - Restrict to your domain: `allow_origins=["https://yourdomain.com"]`

3. **Authentication**:
   - Add user authentication for multi-user deployments
   - Implement rate limiting on WebSocket connections
   - Add request validation

4. **Data Privacy**:
   - Wiki files are stored locally
   - Be aware of API rate limits and costs
   - Consider data retention policies

---

## 📈 Performance Tuning

### Optimize for Speed
```ini
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash-lite  # Fastest
LLM_TEMPERATURE=0.0              # Most deterministic
LLM_MAX_ITERATIONS=3             # Fewer steps
```

### Optimize for Quality
```ini
LLM_PROVIDER=openai
LLM_MODEL=gpt-4-turbo
LLM_TEMPERATURE=0.7              # More creative
LLM_MAX_ITERATIONS=8             # More reasoning
```

### Production Deployment
- Use a reverse proxy (Nginx, Apache) in front of Uvicorn
- Enable gzip compression for responses
- Set up auto-restart with systemd or supervisor
- Monitor WebSocket connections and implement timeouts
- Use environment-based configuration for secrets

---

## 🐛 Troubleshooting

### "API Key not found"
```bash
# Check .env file exists in project root
cat .env
# Should show: GEMINI_API_KEY=xxxxx
```

### "WebSocket connection failed"
```bash
# Check server is running on correct port
netstat -an | findstr 8000  # Windows
lsof -i :8000               # Mac/Linux

# Verify CORS settings in server.py
```

### "Wiki files not visible"
```bash
# Ensure wiki directory exists
mkdir wiki
# Check file permissions
ls -la wiki/
```

### Agent not responding
```bash
# Check API rate limits (especially with free tier)
# Verify LLM_PROVIDER setting matches your API key
# Check internet connection for web search
# Review LLM_MAX_ITERATIONS (too low = incomplete answers)
```

---

## 📚 Example Workflows

### Workflow 1: Learning New Technology
```
User: "Learn about Apache Kafka and create a comprehensive wiki page"
↓
Agent:
  1. Searches web for "Apache Kafka" information
  2. Reads raw file "kafka_notes.txt"
  3. Synthesizes information
  4. Writes "Apache Kafka.md" to wiki
  5. Creates backlinks to "Apache Spark.md"
  6. Returns summary with formatted page
```

### Workflow 2: Research Analysis
```
User: "Analyze this research paper and extract key findings"
↓
Agent:
  1. Reads raw file (PDF text content)
  2. Identifies key concepts and methodologies
  3. Creates "Research Summary.md"
  4. Generates citations and references
  5. Links to related papers in wiki
```

### Workflow 3: Documentation Update
```
User: "Update the trading agents documentation with latest insights"
↓
Agent:
  1. Reads current "TradingAgents.md"
  2. Searches for latest trading AI research
  3. Updates examples and methodologies
  4. Adds new sections on recent advances
  5. Maintains cross-references
```

---

## 🔄 Version History

### V1 (Current)
- ✅ Modular multi-provider architecture
- ✅ FastAPI backend with WebSocket support
- ✅ Modern web UI with real-time streaming
- ✅ Wiki management with file operations
- ✅ Web search integration
- ✅ Support for 4+ LLM providers
- ✅ Configurable agent behavior

### Future Roadmap
- 🔜 Persistent conversation history database
- 🔜 Advanced backlink visualization
- 🔜 File upload and OCR capabilities
- 🔜 Multi-user support with authentication
- 🔜 Export to multiple formats (PDF, HTML, DOCX)
- 🔜 Custom tool creation interface
- 🔜 Schedule regular knowledge updates
- 🔜 Semantic search and embedding-based retrieval

---

## 🤝 Contributing

To improve Wiki-LLM:

1. **Add new providers**: Create a new file in `providers/` extending `BaseProvider`
2. **Add new tools**: Implement in `tools.py` and register in tool declarations
3. **Improve UI**: Enhance the web interface in `ui/`
4. **Documentation**: Update wiki files with examples and use cases

---

## 📜 License

This project is provided as-is for personal and educational use.

---

## ⚡ Key Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | FastAPI, Python | Server and API |
| **Real-time** | WebSockets | Streaming responses |
| **LLM** | Google Generative AI, OpenAI, Anthropic | AI reasoning |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript | Web interface |
| **Knowledge** | Markdown, File system | Knowledge storage |
| **Search** | DuckDuckGo API | Web integration |
| **Config** | Python-dotenv | Environment management |

---

## 🚀 Getting Started Tips

1. **Start Simple**: Begin with basic queries about topics you know
2. **Watch Tool Calls**: Pay attention to what tools the agent uses
3. **Grow Your Wiki**: Let the agent create and link documents
4. **Experiment**: Try different LLM providers to see differences
5. **Customize**: Modify the system prompt in `config.py` for your use case

---

## 📞 Support & Questions

For issues or questions:
1. Check the Troubleshooting section above
2. Review agent logs for error messages
3. Verify environment configuration
4. Test with a simple query first

---

**Built with 🧠 AI Intelligence • Maintained with 📚 Knowledge • Powered by ⚡ LLMs**
