# -*- coding: utf-8 -*-
"""AI 助手对话端点（A2）测试：SSE 事件序 / mock stream_chat / prompt 组装 / 校验"""
import json

import pytest

import main
from fastapi.testclient import TestClient
from services import ai_service as ai
from services import rag_service as rag


async def _fake_stream_ok(messages, *a, **kw):
    """记录收到的 messages，回放固定两片"""
    _fake_stream_ok.messages = messages
    yield "引用测试回答第一片，"
    yield "带 [F1] 编号。"


async def _fake_stream_fail(messages, *a, **kw):
    raise ai.AIConfigError("API Key 无效", code="key_invalid")
    yield  # pragma: no cover


def _sse_events(resp_text: str) -> list[dict | str]:
    out = []
    for line in resp_text.split("\n"):
        if not line.startswith("data: "):
            continue
        d = line[6:]
        out.append("[DONE]" if d == "[DONE]" else json.loads(d))
    return out


def test_chat_sse_event_order_and_done(monkeypatch):
    """事件序：citations 先行 → delta… → [DONE]；citations 与 RAG 命中一致"""
    monkeypatch.setattr(main.ai, "stream_chat", _fake_stream_ok)
    c = TestClient(main.app)
    resp = c.post("/api/v1/assistant/chat", json={"question": "嗓子干喝什么茶"})
    assert resp.status_code == 200
    events = _sse_events(resp.text)
    assert events[-1] == "[DONE]"
    first = events[0]
    assert first["no_context"] is False
    assert first["disclaimer"] == main.DISCLAIMER
    assert first["citations"] and first["citations"][0]["id"].startswith("F")
    deltas = [e for e in events if isinstance(e, dict) and e.get("delta")]
    assert "".join(d["delta"] for d in deltas) == "引用测试回答第一片，带 [F1] 编号。"
    # prompt 注入校验：system 含编号块与红线
    system = _fake_stream_ok.messages[0]["content"]
    assert "[F" in system and "库内资料" in system
    assert "不得输出资料之外的功效主张" in system


def test_chat_no_context_degradation(monkeypatch):
    """无关问题：no_context=true + 空 citations + prompt 声明降级"""
    monkeypatch.setattr(main.ai, "stream_chat", _fake_stream_ok)
    c = TestClient(main.app)
    resp = c.post("/api/v1/assistant/chat", json={"question": "今天天气怎么样"})
    events = _sse_events(resp.text)
    first = events[0]
    assert first["no_context"] is True and first["citations"] == []
    system = _fake_stream_ok.messages[0]["content"]
    assert "按降级规则回答" in system


def test_chat_error_event(monkeypatch):
    """stream_chat 抛 AIConfigError → 流内 error 事件（不是 HTTP 错误）"""
    monkeypatch.setattr(main.ai, "stream_chat", _fake_stream_fail)
    c = TestClient(main.app)
    resp = c.post("/api/v1/assistant/chat", json={"question": "枸杞"})
    events = _sse_events(resp.text)
    errors = [e for e in events if isinstance(e, dict) and e.get("error")]
    assert errors and errors[0]["code"] == "key_invalid"


def test_chat_validation():
    """空问题 422；超长问题 422"""
    c = TestClient(main.app)
    assert c.post("/api/v1/assistant/chat", json={"question": "  "}).status_code == 422
    assert c.post("/api/v1/assistant/chat", json={"question": "茶" * 301}).status_code == 422


def test_build_chat_messages_history_trimming():
    """历史只保留 role/content，最多 6 条（取最近的），单条 500 字截断"""
    history = ([{"role": "system", "content": "junk"}] +
               [{"role": "user" if i % 2 == 0 else "assistant",
                 "content": "x" * 600 if i == 0 else f"m{i}"} for i in range(10)])
    ctx = rag.retrieve_context("嗓子干")
    msgs = ai.build_chat_messages("再来一个", ctx, history, "气虚质")
    roles = [m["role"] for m in msgs]
    assert roles[0] == "system" and roles[-1] == "user"
    assert msgs[-1]["content"] == "再来一个"
    body = msgs[1:-1]
    assert len(body) == 6
    assert all(m["role"] in ("user", "assistant") for m in body)
    # 取的是最近 6 条（m4..m9），早于窗口的超长条目不进入
    assert body[0]["content"] == "m4" and all(len(m["content"]) <= 500 for m in body)
    system = msgs[0]["content"]
    assert "用户体质：气虚质" in system


def test_build_chat_messages_no_context_marker():
    ctx = {"blocks": [], "citations": [], "no_context": True, "total_chars": 0}
    msgs = ai.build_chat_messages("随便聊聊", ctx)
    assert "按降级规则回答" in msgs[0]["content"]
    assert "库内资料" not in msgs[0]["content"] or "（本次检索无命中" in msgs[0]["content"]
