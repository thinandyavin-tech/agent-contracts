import pytest

from agent_contracts import ContractError, RetryPolicy, Tool, ToolRunner


def test_success_has_audit_events():
    tool = Tool("sum", {"a": int, "b": int}, {"total": int}, lambda a, b: {"total": a + b})
    result = ToolRunner().run(tool, {"a": 2, "b": 3})
    assert result.output == {"total": 5}
    assert result.attempts == 1
    assert [event["event"] for event in result.events] == ["tool_attempt", "tool_succeeded"]


def test_contract_failure_retries_then_raises_without_sleep():
    tool = Tool("sum", {"a": int}, {"total": int}, lambda a: {"total": "bad"})
    with pytest.raises(ContractError, match="output"):
        ToolRunner(RetryPolicy(max_attempts=2), sleep=lambda _: None).run(tool, {"a": 1})


def test_transient_failure_recovers():
    calls = 0
    def handler():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary")
        return {"ok": True}
    tool = Tool("unstable", {}, {"ok": bool}, handler)
    result = ToolRunner(RetryPolicy(max_attempts=2), sleep=lambda _: None).run(tool, {})
    assert result.attempts == 2
