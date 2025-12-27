## Installation Guide for ADAPT Framework

### Quick Start

```bash
# Install from PyPI (when published)
pip install adapt-framework

# Or install from source
git clone https://github.com/yourusername/ADAPT.git
cd ADAPT
pip install -e .
```

### Installation Options

ADAPT provides several installation profiles depending on your needs:

#### Minimal Installation
```bash
pip install adapt-framework
```
Includes core functionality only.

#### Development Installation
```bash
pip install adapt-framework[dev]
```
Includes testing, linting, and type checking tools.

#### Complete Installation
```bash
pip install adapt-framework[all]
```
Includes all optional dependencies:
- Analytics (numpy, pandas, scipy)
- Connectors (Prometheus, Elasticsearch, AWS)
- LLM providers (OpenAI, Anthropic)
- Visualizations (matplotlib, networkx)
- Integrations (GitHub, Jira, Slack)
- Database support (Neo4j, Redis)
- API server (FastAPI, Uvicorn)

#### Custom Installation
```bash
# LLM support only
pip install adapt-framework[llm]

# Connectors only
pip install adapt-framework[connectors]

# API server
pip install adapt-framework[server]

# Multiple profiles
pip install adapt-framework[llm,connectors,server]
```

### Development Setup

#### 1. Clone Repository
```bash
git clone https://github.com/yourusername/ADAPT.git
cd ADAPT
```

#### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 3. Install in Development Mode
```bash
pip install -e .[dev]
```

#### 4. Verify Installation
```bash
# Test CLI
adapt --version

# Run Python import test
python -c "from core import RCAOrchestrator; print('✓ Installation successful')"

# Run test suite
pytest
```

### Environment Configuration

Create a `.env` file or export environment variables:

```bash
# Logging
export ADAPT_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
export ADAPT_LOG_FORMAT=json  # json or text

# LLM Configuration
export ANTHROPIC_API_KEY=sk-ant-xxx
export OPENAI_API_KEY=sk-xxx

# Optional: Database
export NEO4J_PASSWORD=your-password
export REDIS_URL=redis://localhost:6379

# Optional: Integrations
export GITHUB_TOKEN=ghp_xxx
export JIRA_API_TOKEN=xxx
export SLACK_BOT_TOKEN=xoxb-xxx
```

### Verifying Type Checking Support

ADAPT includes `py.typed` markers for type checking:

```bash
# Install mypy
pip install mypy

# Check types in your code
mypy your_script.py

# Example
cat > test_types.py << 'EOF'
from core import RCAOrchestrator, ADAPTConfig

config = ADAPTConfig()
orchestrator = RCAOrchestrator(config)
# mypy will validate all types!
EOF

mypy test_types.py
```

### Troubleshooting

#### Import Errors
If you see `ModuleNotFoundError: No module named 'core'`:
```bash
# Ensure you're in the correct directory
cd /path/to/ADAPT

# Reinstall in development mode
pip install -e .
```

#### Missing Dependencies
```bash
# Install all dependencies
pip install -e .[all]

# Or update requirements
pip install --upgrade -r requirements.txt
```

#### Permission Errors
On macOS/Linux:
```bash
# Use --user flag if you don't have admin rights
pip install --user -e .
```

### Platform-Specific Notes

#### macOS
```bash
# Install Xcode Command Line Tools if needed
xcode-select --install
```

#### Windows
```bash
# Use PowerShell or Command Prompt
python -m venv venv
venv\Scripts\activate
pip install -e .[dev]
```

#### Linux
```bash
# Install Python development headers
sudo apt-get install python3-dev  # Debian/Ubuntu
sudo yum install python3-devel     # RHEL/CentOS
```

### Docker Installation

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install -e .[all]

CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Build and run
docker build -t adapt-framework .
docker run -p 8000:8000 adapt-framework
```

### Next Steps

- Read the [Quick Start Guide](../README.md#quick-start)
- Explore [Example Playbooks](../playbooks/)
- Review [Architecture Documentation](architecture.md)
- Join the community discussions

