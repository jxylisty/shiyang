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
            "三维评分均值(抗炎/免疫/气道修复)": analysis.get("radar_summary"),
            "主要靶点": [t["gene"] for t in (analysis.get("top_targets") or [])[:6]],
        }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "请解读这个方子：\n" + json.dumps(info, ensure_ascii=False, indent=1)},
    ]


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
