# ACE (Agentic Context Engineering) Implementation

## Overview

This implementation of **ACE (Agentic Context Engineering)** is based on the 2024 research paper "[Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models](https://arxiv.org/abs/2510.04618)" by Zhang et al.

ACE enables LLM agents to self-improve by treating contexts as **evolving playbooks** that accumulate, refine, and organize strategies through generation, reflection, and curation.

## Key Components

### 1. **Generator** (Agent)
Located in: `app/agent/agent.py`

The Generator produces reasoning trajectories for tasks, highlighting both effective strategies and common pitfalls.

**Features:**
- Multi-step agentic loop with tool calling
- Integrates ACE playbook into system prompt
- Streams real-time updates to the frontend

### 2. **Reflector**
Located in: `app/ace/reflector.py`

The Reflector analyzes execution outcomes and extracts concrete insights.

**Capabilities:**
- Diagnoses failure modes and successes
- Identifies missing heuristics or rules
- Provides iterative refinement (up to 5 rounds)
- Tags playbook bullets as helpful/harmful/neutral

**Output:**
- Error identification
- Root cause analysis
- Correct approach recommendations
- Key insights and principles

### 3. **Curator**
Located in: `app/ace/curator.py`

The Curator synthesizes reflections into structured delta updates.

**Responsibilities:**
- Converts insights into actionable operations
- Avoids redundancy with existing knowledge
- Applies incremental delta updates
- Maintains playbook quality and organization

**Operations:**
- `ADD`: Create new bullet points
- `UPDATE`: Modify existing bullets
- `REMOVE`: Delete outdated bullets

### 4. **Playbook**
Located in: `app/ace/playbook.py`

The Playbook is a structured collection of knowledge bullets organized by section.

**Structure:**
- **Strategies and Hard Rules**: General strategies and important rules
- **Useful Code Snippets**: Code patterns and templates
- **Troubleshooting and Pitfalls**: Common errors and solutions
- **APIs and Schemas**: API usage patterns and response formats
- **Domain Knowledge**: Domain-specific concepts and facts

**Features:**
- Incremental delta updates (not monolithic rewrites)
- Grow-and-refine mechanism with deduplication
- Bullet tracking with helpful/harmful counters
- Serialization support for persistence

## Architecture

```
┌─────────────┐
│   User      │
│   Query     │
└──────┬──────┘
       │
       v
┌─────────────────────────────────────┐
│         Generator (Agent)           │
│  - Produces reasoning trajectories  │
│  - Uses playbook context           │
│  - Executes tools                  │
└──────┬──────────────────────────────┘
       │
       │ Trajectory
       v
┌─────────────────────────────────────┐
│        Reflector                    │
│  - Analyzes outcomes               │
│  - Extracts insights               │
│  - Iterative refinement            │
└──────┬──────────────────────────────┘
       │
       │ Insights
       v
┌─────────────────────────────────────┐
│         Curator                     │
│  - Synthesizes delta updates       │
│  - Avoids redundancy               │
│  - Applies operations              │
└──────┬──────────────────────────────┘
       │
       │ Delta Operations
       v
┌─────────────────────────────────────┐
│        Playbook                     │
│  - Structured bullets              │
│  - Grow and refine                 │
│  - Deduplication                   │
└─────────────────────────────────────┘
```

## Key Innovations

### 1. **Incremental Delta Updates**
Instead of monolithic context rewrites, ACE uses localized, incremental updates:
- Reduces latency by **86.9%** on average
- Reduces token costs by **83.6%**
- Prevents context collapse

### 2. **Grow-and-Refine Mechanism**
The playbook grows steadily while maintaining quality:
- New bullets are appended with unique IDs
- Existing bullets are updated in-place
- Periodic deduplication removes redundancy
- Harmful bullets are pruned automatically

### 3. **Structured Bullets**
Each bullet contains:
- **ID**: Unique identifier for tracking
- **Section**: Organizational category
- **Content**: The actual knowledge/strategy
- **Counters**: Helpful and harmful vote counts
- **Metadata**: Additional context

## Usage

### Basic Agent with ACE

```python
from app.agent import Agent

# Create agent with ACE enabled (default)
agent = Agent(
    workspace_path="/path/to/workspace",
    enable_ace=True  # Enable ACE self-improvement
)

# Process a message
async for event in agent.process_message("Implement feature X"):
    print(event)

# Learn from the interaction (typically called after task completion)
await agent.learn_from_interaction(
    task="Implement feature X",
    trajectory=execution_trace,
    outcome={"success": True, "files_modified": 2}
)

# Save learned knowledge
agent.save_playbook("playbooks/workspace_playbook.json")
```

### Disable ACE

```python
# Create agent without ACE
agent = Agent(
    workspace_path="/path/to/workspace",
    enable_ace=False  # Traditional agent without self-improvement
)
```

### Load Existing Playbook

```python
agent = Agent(workspace_path="/path/to/workspace")

# Load previously learned knowledge
agent.load_playbook("playbooks/workspace_playbook.json")
```

## Performance Benefits

Based on the original ACE paper:

| Metric | Improvement |
|--------|-------------|
| **Agent Tasks (AppWorld)** | +10.6% accuracy |
| **Domain-Specific (Finance)** | +8.6% accuracy |
| **Adaptation Latency** | -86.9% reduction |
| **Token Dollar Cost** | -83.6% reduction |
| **Rollouts Required** | -75.1% reduction |

## Self-Improvement Without Labels

ACE can learn effectively **without ground-truth labels** by leveraging:
- Execution feedback (code success/failure)
- Environment signals (test results, errors)
- Natural language critique
- Tool execution outcomes

## Offline vs Online Adaptation

### Offline Adaptation
- Optimize on training data
- Build comprehensive playbook upfront
- Use for system prompt optimization

### Online Adaptation
- Adapt during test time
- Accumulate knowledge from each interaction
- Continuous learning from user feedback

## Implementation Details

### Reflector Prompts
The Reflector uses structured prompts to extract:
1. **Reasoning**: Detailed chain-of-thought analysis
2. **Error Identification**: What specifically went wrong
3. **Root Cause Analysis**: Why the error occurred
4. **Correct Approach**: What should have been done
5. **Key Insight**: Principles to remember

### Curator Operations
The Curator generates delta operations in JSON format:
```json
{
  "reasoning": "Analysis of what needs to be added...",
  "operations": [
    {
      "type": "ADD",
      "section": "strategies_and_hard_rules",
      "content": "Always validate input before processing"
    }
  ]
}
```

### Playbook Serialization
Playbooks are saved in JSON format for persistence across sessions:
```json
{
  "bullets": {
    "str-a1b2c3d4": {
      "id": "str-a1b2c3d4",
      "section": "strategies_and_hard_rules",
      "content": "Read files before modifying them",
      "helpful_count": 5,
      "harmful_count": 0
    }
  },
  "sections": {
    "strategies_and_hard_rules": ["str-a1b2c3d4"]
  }
}
```

## Research Citations

If you use this implementation, please cite the original paper:

```bibtex
@article{zhang2024ace,
  title={Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models},
  author={Zhang, Qizheng and Hu, Changran and Upasani, Shubhangi and Ma, Boyuan and Hong, Fenglu and Kamanuru, Vamsidhar and Rainton, Jay and Wu, Chen and Ji, Mengmeng and Li, Hanchen and Thakker, Urmish and Zou, James and Olukotun, Kunle},
  journal={arXiv preprint arXiv:2510.04618},
  year={2024}
}
```

## Sources

- [ACE Paper (arXiv)](https://arxiv.org/abs/2510.04618)
- [ACE GitHub Repository](https://github.com/ace-agent/ace)
- [VentureBeat Article on ACE](https://venturebeat.com/ai/ace-prevents-context-collapse-with-evolving-playbooks-for-self-improving-ai)
- [Medium Article on ACE](https://medium.com/@jannadikhemais/agentic-context-engineering-ace-fea25fb05cdd)

## Future Enhancements

Potential improvements to this implementation:
1. **Embedding-based deduplication** using semantic similarity
2. **Multi-epoch adaptation** for offline training
3. **Retrieval-augmented playbook** for large contexts
4. **Hierarchical playbook** organization
5. **Collaborative playbook** sharing across agents
6. **Automatic prompt optimization** using ACE insights
