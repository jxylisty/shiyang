# -*- coding: utf-8 -*-
"""
AI 流式解读服务（移植自大创系统 ai_service，OpenAI/DeepSeek 兼容）
Key 由前端请求头传入，不落库。含食养报告专用 prompt 组装。
P2 新增：平台级 Key 预生成解读（pregen），无用户 Key 也能流式回放。
"""
import json
import os
import sqlite3
from pathlib import Path
from typing import AsyncIterator

import httpx

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"

# 三维机制评分的维度源自大创课题呼吸机制框架，仅适用于这些场景的方子
RESP_SCENES = {"护嗓润喉", "久坐通气"}

PROVIDER_DEFAULTS = {
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o"},
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
}


class AIConfigError(Exception):
    def __init__(self, message: str, code: str = "config_error"):
        self.message, self.code = message, code
        super().__init__(message)


def resolve_provider(provider: str, base_url: str, model: str):
    provider = provider if provider in PROVIDER_DEFAULTS else "deepseek"
    d = PROVIDER_DEFAULTS[provider]
    return base_url or d["base_url"], model or d["model"]


async def stream_chat(messages, api_key, provider="deepseek", base_url="", model="",
                      temperature=0.6, timeout=120.0) -> AsyncIterator[str]:
    if not api_key or not api_key.strip():
        raise AIConfigError("未配置 AI API Key", code="key_missing")
    base_url, model = resolve_provider(provider, base_url, model)
    headers = {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "stream": True, "temperature": temperature}
    # 显式代理：本机常挂 socks 代理而 httpx 需 socksio 才能走 socks5，
    # 用 HTTP 代理口（HTTPS_PROXY）作为兜底，避免 socksio 缺包崩溃
    proxy = None
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if https_proxy:
        proxy = https_proxy
    async with httpx.AsyncClient(timeout=timeout, proxy=proxy) as client:
        async with client.stream("POST", f"{base_url.rstrip('/')}/chat/completions",
                                 headers=headers, json=payload) as resp:
            if resp.status_code == 401:
                raise AIConfigError("API Key 无效", code="key_invalid")
            if resp.status_code == 402:
                raise AIConfigError("API 额度耗尽", code="quota_exhausted")
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0]["delta"]
                    if delta.get("content"):
                        yield delta["content"]
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue


SYSTEM_PROMPT = """你是「食养有据」平台的食养科普助手。用户会给你一个茶饮/药膳方的配料、来源和成分分析数据。
请用通俗友好的中文写一份 300 字左右的解读，结构：
1. 一句话讲清这个方的传统定位（引用配料功效逻辑，不要夸大）
2. 结合成分数据（入血概率、三维评分）解释"凭什么值得喝"，把专业术语翻译成人话
3. 冲泡/食用小贴士和禁忌提醒
关于三维评分：其维度（抗炎/免疫调节/气道修复）来自本团队大创数据库的 Enrichr 通路富集分析，
仅当输入数据里出现"三维评分"字段时才可提及，且只作为成分靶点富集倾向的一般性参考，
不得将其表述为该方对某场景的功效证明；若数据中没有该字段，不要自行编造此类评分。
关于入血概率：它表示成分"在血中被检出的倾向"，不等于口服吸收率。不要用"吸收率""生物利用度"来解释它；
若某成分分子量大但概率高，不要声称它"容易被吸收"，应说明其血中检出有文献依据。
数据来源为南京中医药大学自建 ccTCM 2.0 数据库，必要时可说明。
红线：绝不使用"治疗、疗效、治愈、抗癌"字样；必须保留"调理参考，不构成医疗建议"的定位；
不确定的内容直说不确定；成分数据引用时保留数值。"""


def build_recipe_messages(recipe: dict, analysis: dict | None) -> list[dict]:
    mats = "、".join(
        f"{m['name']}({m['grams']}g)" if m.get("grams") else m["name"]
        for m in recipe.get("materials", []))
    info = {
        "方名": recipe.get("name"), "类型": recipe.get("type"),
        "配料": mats, "传统定位": recipe.get("oneliner"),
        "来源": recipe.get("source"),
        "适宜体质": recipe.get("constitutions_suitable"),
        "禁忌": recipe.get("contraindication"),
    }
    if analysis:
        info["成分分析"] = {
            "化合物总数": analysis.get("compound_count"),
            "高入血概率成分Top5": [
                {"名称": c.get("name"), "入血概率": c.get("prob_cctcm"), "来自": c.get("herbs", "")}
                for c in (analysis.get("top_compounds") or [])[:5]],
            "主要靶点": [t["gene"] for t in (analysis.get("top_targets") or [])[:6]],
        }
        # 三维维度是呼吸机制框架，只给呼吸/咽喉相关方子，避免 AI 对助眠/祛痘类强行解释"气道修复"
        if RESP_SCENES & set(recipe.get("scenes") or []):
            rs = analysis.get("radar_summary")
            if isinstance(rs, dict):
                rs = {k: v for k, v in rs.items()
                      if k in ("anti_inflammatory", "immune_regulation", "airway_repair")}
            info["成分分析"]["三维评分均值(抗炎/免疫/气道修复，Enrichr 通路富集)"] = rs
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "请解读这个方子：\n" + json.dumps(info, ensure_ascii=False, indent=1)},
    ]


# ---------- AI 助手对话（T3-11：RAG 限定库内资料 + 强制引用编号） ----------

CHAT_SYSTEM_PROMPT = """你是「食养有据」平台的食养问答助手，回答基于平台方子库/药材库/成分库的检索资料。

铁律（优先级最高）：
1. 回答必须仅基于下方「库内资料」；资料没有的直接说「知识库未收录，你可以在顶部搜索里换个关键词试试」，不编造方子、药材、成分或数据。
2. 提及任何方子/药材/成分时必须带上其编号，如 [F12][H3][C5]，用户能点开引用卡核对出处。
3. 不得输出资料之外的功效主张；不使用「治疗、疗效、治愈、抗癌」字样；不说「包治」「根治」。
4. 入血概率是模型预测值，不等于吸收率/生物利用度，引用时保留数值并说明是预测。
5. 禁忌信息（资料中给出时）必须提醒；涉及疾病症状建议就医，保持「健康参考，不构成医疗建议」定位。

风格：通俗友好的中文，100~250 字；可以先一句话回应需求，再列资料里最对口的 1-3 个方子或要点；
适合的方子给一句「为什么适合」（体质/场景/配料逻辑），引用编号紧跟在名称后。
库内资料为空时（无「库内资料」段）：只回答一般性食养常识（如喝水规律、作息建议），
并必须在回答第一行写明「（以下回答未引用库内数据，仅供参考）」。"""


def build_chat_messages(question: str, context: dict, history: list[dict] | None = None,
                        constitution_name: str | None = None) -> list[dict]:
    """RAG 资料 + 会话历史 → 对话 messages。

    context 为 rag_service.retrieve_context() 的返回；no_context 时不给「库内资料」段，
    由 system prompt 让模型第一行声明降级。history 只保留 role/content。
    """
    parts = [CHAT_SYSTEM_PROMPT]
    if constitution_name:
        parts.append(f"用户体质：{constitution_name}（来自平台体质测评，可作为方子适宜度参考，非医学结论）。")
    if context and context.get("blocks"):
        parts.append("库内资料（每条以 [F#]/[H#]/[C#] 编号，引用时必须保留编号）：\n"
                     + "\n".join(f"- {b}" for b in context["blocks"]))
    else:
        parts.append("库内资料：（本次检索无命中，按降级规则回答）")
    parts.append(f"用户问题：{question}")
    system = "\n\n".join(parts)

    msgs: list[dict] = [{"role": "system", "content": system}]
    for m in (history or [])[-6:]:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": content[:500]})
    msgs.append({"role": "user", "content": question})
    return msgs


# ---------- 预生成解读（P2：AI 免门槛） ----------

def _pregen_db():
    """预生成表建在 shiyang.db（方子库一侧），与 recipe_analysis 同库方便同事务"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS recipe_pregen_ai (
        recipe_id INTEGER PRIMARY KEY REFERENCES recipe(id),
        content TEXT NOT NULL,
        model TEXT,
        generated_at TEXT DEFAULT (datetime('now'))
    )""")
    return conn


def get_pregen_report(recipe_id: int) -> str | None:
    conn = _pregen_db()
    try:
        row = conn.execute("SELECT content FROM recipe_pregen_ai WHERE recipe_id=?", (recipe_id,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def save_pregen_report(recipe_id: int, content: str, model: str = ""):
    conn = _pregen_db()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO recipe_pregen_ai(recipe_id,content,model) VALUES (?,?,?)",
            (recipe_id, content, model))
        conn.commit()
    finally:
        conn.close()


def platform_key() -> str | None:
    """平台级 Key：环境变量 SHIYANG_AI_KEY（生成预解读用，不经过前端）"""
    key = os.environ.get("SHIYANG_AI_KEY") or ""
    return key.strip() or None


def pregen_missing(limit: int | None = None) -> list[int]:
    """找出 analysis_ready=1 但还没有预生成解读的方子 id（一次性脚本用）"""
    conn = _pregen_db()
    try:
        sql = ("SELECT r.id FROM recipe r LEFT JOIN recipe_pregen_ai p ON p.recipe_id=r.id "
               "WHERE r.analysis_ready=1 AND p.recipe_id IS NULL ORDER BY r.id")
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [r[0] for r in conn.execute(sql).fetchall()]
    finally:
        conn.close()
