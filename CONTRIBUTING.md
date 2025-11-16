# Contributing to ADAPT

Thank you for your interest in contributing to ADAPT! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)

## Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please be respectful and constructive in all interactions.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/yourusername/ADAPT.git
   cd ADAPT
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/original/ADAPT.git
   ```

## Development Setup

### Prerequisites

- Python 3.9 or higher
- pip and virtualenv

### Setup Steps

1. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

3. **Install development dependencies**:
   ```bash
   pip install pytest pytest-cov pytest-asyncio black mypy ruff
   ```

4. **Verify installation**:
   ```bash
   python -c "import core; print('ADAPT installed successfully')"
   ```

## How to Contribute

### Reporting Bugs

- Use GitHub Issues
- Include a clear title and description
- Provide steps to reproduce
- Include error messages and stack traces
- Specify your environment (OS, Python version, etc.)

### Suggesting Features

- Use GitHub Issues with the "enhancement" label
- Explain the use case and benefits
- Consider implementation approaches
- Be open to discussion

### Contributing Code

We welcome contributions in these areas:

1. **New Connectors**: Add support for new data sources
2. **New Agents**: Create specialized diagnostic agents
3. **Playbooks**: Add incident scenario playbooks
4. **Bug Fixes**: Fix reported issues
5. **Documentation**: Improve docs and examples
6. **Tests**: Increase test coverage

## Coding Standards

### Python Style

We follow PEP 8 with some modifications:

- **Line length**: 100 characters (not 79)
- **Formatting**: Use Black for code formatting
- **Imports**: Use isort for import sorting
- **Type hints**: Use type hints for all function signatures
- **Docstrings**: Use Google-style docstrings

### Example

```python
from typing import List, Optional
from datetime import datetime


class MyAgent(BaseAgent):
    """
    A sample diagnostic agent.

    This agent demonstrates proper code style and documentation.

    Attributes:
        name: The agent's unique identifier
        config: Configuration dictionary
    """

    def __init__(self, name: str, config: Optional[dict] = None):
        """
        Initialize the agent.

        Args:
            name: Unique name for this agent
            config: Optional configuration dictionary
        """
        super().__init__(name, config)
        self.threshold = config.get('threshold', 0.8) if config else 0.8

    async def execute(self, context: OrchestrationContext) -> AgentResult:
        """
        Execute the agent's diagnostic logic.

        Args:
            context: The orchestration context containing signals and graph

        Returns:
            AgentResult containing findings and metadata

        Raises:
            ValueError: If context is invalid
        """
        # Implementation here
        pass
```

### Code Quality Tools

Run these before submitting:

```bash
# Format code
black .

# Check types
mypy core agents connectors

# Lint code
ruff check .

# Run tests
pytest
```

## Testing

### Writing Tests

- Place tests in the `tests/` directory
- Use pytest for all tests
- Name test files `test_*.py`
- Use async test functions for async code

### Example Test

```python
import pytest
from core.rca_graph import RCAGraph, RCANode, NodeType


@pytest.mark.asyncio
async def test_rca_graph_creation():
    """Test basic RCA graph creation."""
    graph = RCAGraph(incident_id="test_001")

    node = RCANode(
        id="symptom_1",
        type=NodeType.SYMPTOM,
        title="Test Symptom",
        description="A test symptom"
    )

    graph.add_node(node)

    assert graph.get_node("symptom_1") == node
    assert len(graph.nodes) == 1
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=core --cov=agents --cov=connectors

# Run specific test
pytest tests/test_rca_graph.py::test_rca_graph_creation

# Run with verbose output
pytest -v
```

## Submitting Changes

### Branch Naming

Use descriptive branch names:

- `feature/add-prometheus-connector`
- `bugfix/fix-metric-analyzer-crash`
- `docs/improve-readme`
- `test/add-orchestrator-tests`

### Commit Messages

Write clear, concise commit messages:

- Use present tense ("Add feature" not "Added feature")
- First line: brief summary (50 chars or less)
- Blank line, then detailed description if needed

Example:
```
Add Prometheus connector for metric ingestion

- Implement PrometheusConnector class
- Add PromQL query support
- Include connection pooling
- Add unit tests and documentation
```

### Pull Request Process

1. **Create a branch**:
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make your changes**:
   - Write code
   - Add tests
   - Update documentation

3. **Test your changes**:
   ```bash
   pytest
   black .
   mypy core agents connectors
   ```

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Add my feature"
   ```

5. **Push to your fork**:
   ```bash
   git push origin feature/my-feature
   ```

6. **Create a Pull Request** on GitHub:
   - Provide a clear description
   - Reference any related issues
   - Include screenshots if applicable

7. **Address review feedback**:
   - Respond to comments
   - Make requested changes
   - Push updates to the same branch

### PR Checklist

Before submitting, ensure:

- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] Type hints added
- [ ] No unnecessary dependencies added
- [ ] Commit messages are clear
- [ ] PR description is complete

## Review Process

- Maintainers will review your PR
- Feedback may be provided
- Changes may be requested
- Once approved, your PR will be merged

## Recognition

Contributors will be:
- Listed in the project's contributors
- Mentioned in release notes
- Thanked in the community

## Questions?

- Open a GitHub Discussion
- Ask in the community chat
- Email the maintainers

Thank you for contributing to ADAPT! 🎉
