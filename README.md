# Agent Contracts

Schema-first tool execution for reliable AI agents.

`agent-contracts` turns ad-hoc tool calls into typed, observable operations. It validates input and output, applies bounded retries, enforces timeouts, and emits structured audit events that can be sent to your existing webhook or analytics stack.

## Why

Production agents need the same guarantees as other distributed systems: explicit contracts, failure boundaries, deterministic tests, and useful telemetry. This package has no model-provider dependency, so the policy layer can sit in front of OpenAI-compatible, local, or mocked tools.

## Quick start

```python
from agent_contracts import Tool, ToolRunner, RetryPolicy

weather = Tool(name="weather", input_schema={"city": str}, output_schema={"temperature_c": float}, handler=lambda city: {"temperature_c": 31.0})
runner = ToolRunner(retry_policy=RetryPolicy(max_attempts=2))
result = runner.run(weather, {"city": "Chiang Mai"})
print(result.output, result.attempts)
```

## Features

- Runtime input/output contracts with clear validation errors
- Exponential backoff with jitter-free deterministic delays for testing
- Per-call timeout and concurrency-safe circuit breaker
- JSON-serializable audit events for traces and billing
- Provider-agnostic, dependency-free Python 3.11+

## Development

```bash
python -m pip install -e ".[dev]"
pytest -q
ruff check .
```

MIT licensed. See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
