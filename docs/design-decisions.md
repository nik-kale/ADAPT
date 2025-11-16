# Design Decisions

This document captures the key design decisions made in building the ADAPT framework and the rationale behind them.

## 1. Graph-Based RCA Model

**Decision**: Use a directed graph to represent the RCA process rather than a linear chain or hierarchical tree.

**Rationale**:
- **Flexibility**: Real-world incidents often have multiple symptoms, hypotheses, and contributing factors
- **Expressiveness**: Graphs naturally represent causal relationships and dependencies
- **Traceability**: Can traverse from symptom to root cause or reverse
- **Visualization**: Graph structure translates well to visual representations

**Alternatives Considered**:
- Linear diagnostic chain: Too rigid for complex incidents
- Hierarchical tree: Cannot represent multiple parents/causes
- Unstructured findings list: Loses causal relationships

## 2. Multi-Agent Architecture

**Decision**: Implement specialized agents rather than a monolithic analyzer.

**Rationale**:
- **Separation of Concerns**: Each agent focuses on one diagnostic domain
- **Modularity**: Easy to add, remove, or replace agents
- **Parallel Execution**: Independent agents can run concurrently
- **Maintainability**: Smaller, focused codebases are easier to maintain
- **Specialization**: Each agent can use domain-specific techniques

**Alternatives Considered**:
- Single monolithic analyzer: Would become unwieldy and hard to extend
- Plugin-based system: More complex without significant benefits
- External service calls: Added latency and operational complexity

## 3. Async/Await for Orchestration

**Decision**: Use Python's async/await for agent coordination and I/O operations.

**Rationale**:
- **Concurrency**: Multiple agents can run simultaneously
- **Efficiency**: Non-blocking I/O for connector operations
- **Scalability**: Better resource utilization under load
- **Modern Python**: Aligns with contemporary Python best practices

**Alternatives Considered**:
- Threading: More complex, GIL limitations, harder to debug
- Multiprocessing: Overhead of process spawning, data serialization
- Synchronous: Sequential execution would be much slower

## 4. Signal Normalization Layer

**Decision**: Normalize all telemetry data into a unified `NormalizedSignal` format before analysis.

**Rationale**:
- **Abstraction**: Agents don't need to know about specific data sources
- **Consistency**: Uniform interface for all signal types
- **Extensibility**: Easy to add new data sources
- **Testability**: Can mock signals without real data sources
- **Transformation Logic Centralized**: Conversion logic in one place

**Alternatives Considered**:
- Direct connector access: Would tightly couple agents to connectors
- Per-agent normalization: Duplicated logic across agents
- No normalization: Agents would need source-specific code

## 5. Playbook-Driven Analysis

**Decision**: Use YAML playbooks to define incident scenarios and guide analysis.

**Rationale**:
- **Domain Knowledge Capture**: Encode incident patterns and best practices
- **Consistency**: Standardized approach to common incidents
- **Customization**: Teams can define their own playbooks
- **Learning Tool**: New users can understand RCA workflows
- **Human-Readable**: YAML is accessible to non-developers

**Alternatives Considered**:
- Code-based definitions: Less accessible to operations teams
- Database-stored playbooks: Added infrastructure dependency
- No playbooks: Would lose domain knowledge encoding

## 6. Confidence Scoring System

**Decision**: Assign confidence scores (0.0 to 1.0) to findings and root causes.

**Rationale**:
- **Uncertainty Representation**: RCA is inherently probabilistic
- **Prioritization**: Focus on high-confidence findings first
- **Transparency**: Users understand certainty level
- **Threshold-Based Actions**: Can trigger actions at confidence thresholds
- **Agent Comparison**: Identify which agents are most reliable

**Alternatives Considered**:
- Binary (yes/no): Too simplistic for real-world complexity
- Categories (low/medium/high): Less granular
- No confidence: Would treat all findings equally

## 7. Python as Implementation Language

**Decision**: Use Python for core framework implementation.

**Rationale**:
- **AI/ML Ecosystem**: Rich libraries for LLM integration, data analysis
- **Async Support**: Native async/await for concurrent operations
- **Readability**: Clear, maintainable code
- **Adoption**: Widely used in DevOps and SRE communities
- **Rapid Prototyping**: Quick iteration during development

**Alternatives Considered**:
- Go: Better performance but less AI/ML ecosystem
- TypeScript/Node.js: Good async but weaker data science tools
- Rust: Excellent performance but steeper learning curve

## 8. Stateless Orchestrator Design

**Decision**: Make the RCAOrchestrator stateless; all state lives in OrchestrationContext.

**Rationale**:
- **Scalability**: Can run multiple orchestrators in parallel
- **Testability**: Easy to test with different contexts
- **Serialization**: Context can be saved/resumed
- **Simplicity**: No shared state management needed
- **Cloud-Native**: Aligns with stateless microservice patterns

**Alternatives Considered**:
- Stateful orchestrator: Would limit horizontal scaling
- Database-backed state: Added complexity and latency
- Singleton pattern: Not cloud-native, hard to scale

## 9. Connector Abstraction

**Decision**: Define a `BaseConnector` abstract class that all data sources implement.

**Rationale**:
- **Pluggability**: Swap data sources without changing agents
- **Interface Consistency**: All connectors have same methods
- **Testability**: Easy to create mock connectors
- **Extensibility**: Add new sources by implementing interface
- **Separation**: Data access logic separate from analysis

**Alternatives Considered**:
- Direct API calls: Would couple framework to specific tools
- Unified connector: Single connector for all sources (too complex)
- No abstraction: Each agent handles its own data fetching

## 10. Remediation Planning as Separate Agent

**Decision**: Make remediation planning a distinct agent rather than built into orchestrator.

**Rationale**:
- **Modularity**: Can disable remediation if not needed
- **Customization**: Teams can implement custom remediation logic
- **Separation**: Analysis separate from action planning
- **Reusability**: Remediation templates can be shared
- **Safety**: Clearly separates diagnostic from prescriptive actions

**Alternatives Considered**:
- Built-in remediation: Less flexible, harder to customize
- External service: Added operational complexity
- No remediation: Incomplete solution for users

## 11. JSON and Markdown Output Formats

**Decision**: Support both structured (JSON) and human-readable (Markdown) outputs.

**Rationale**:
- **API Integration**: JSON for programmatic access
- **Human Consumption**: Markdown for incident reports
- **Flexibility**: Users choose format based on use case
- **Complete Data**: JSON preserves all graph structure
- **Readability**: Markdown provides narrative flow

**Alternatives Considered**:
- JSON only: Not human-friendly
- Markdown only: Loses structured data
- HTML: More complex, rendering dependencies

## 12. Synthetic Connector for Testing

**Decision**: Include a synthetic data connector in the framework.

**Rationale**:
- **Testing**: Enables testing without real infrastructure
- **Demos**: Easy to demonstrate framework capabilities
- **Development**: Developers can work without backend access
- **Reproducibility**: Same data every time for consistent tests
- **Learning**: New users can explore without setup

**Alternatives Considered**:
- Mock data in tests: Would duplicate across test files
- Require real connectors: High barrier to entry
- No test data: Harder for users to get started

## 13. Type Hints and Dataclasses

**Decision**: Use Python type hints and dataclasses throughout the codebase.

**Rationale**:
- **Type Safety**: Catch errors at development time
- **IDE Support**: Better autocomplete and refactoring
- **Documentation**: Types serve as inline documentation
- **Validation**: Runtime validation with type checkers
- **Maintainability**: Easier to understand code intent

**Alternatives Considered**:
- No type hints: Less safe, harder to maintain
- Manual validation: More code, error-prone
- Pydantic models: Added dependency, more complex

## 14. Agent Results as Structured Data

**Decision**: Return structured `AgentResult` objects rather than free-form dictionaries.

**Rationale**:
- **Consistency**: All agents return same structure
- **Validation**: Enforced result format
- **Type Safety**: Type hints ensure correctness
- **Documentation**: Clear what agents should return
- **Testability**: Easy to validate agent outputs

**Alternatives Considered**:
- Free-form dicts: Inconsistent, error-prone
- JSON strings: Requires parsing, no type safety
- Custom per agent: Inconsistent interface

## 15. Adaptive Execution Mode

**Decision**: Include adaptive execution mode that adjusts agent order based on results.

**Rationale**:
- **Efficiency**: Focus computational resources where needed
- **Intelligence**: Framework learns what to investigate
- **Cost Optimization**: Avoid running unnecessary agents
- **User Experience**: Faster time to root cause
- **Flexibility**: Adapts to different incident types

**Alternatives Considered**:
- Sequential only: Slower, wastes resources
- Parallel only: May run unnecessary agents
- Fixed priority: Not adaptive to incident specifics

## Future Considerations

These decisions may evolve as the framework matures:

1. **LLM Integration**: Direct integration with LLM APIs for agent reasoning
2. **Streaming Results**: Stream agent findings as they're discovered
3. **Distributed Execution**: Run agents across multiple machines
4. **Graph Database**: Store RCA graphs in specialized database
5. **Real-time Mode**: Continuous RCA as incidents develop
