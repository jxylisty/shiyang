# -*- coding: utf-8 -*-
"""
「说人话」白话解读服务（大众层）

产品分层：大众默认只看白话解读 + 配方做法禁忌；入血概率/靶点/网络图等研究分析
收进「专业模式」。本服务负责把方子的传统功效翻译成普通人能看懂的话。

数据性质（AGENTS.md §2.3/§2.6）：
- AI 改写仅使用方子库里已有的传统资料。自定义方子也可显示依据已收录单味资料整理的
  简明卡片，两种来源分别标注。
- 内容尚未经医药背景人员审校，接口返回 reviewed=False，前端如实提示。

存储：
- 已有方子：离线脚本 scripts/pregen_plain.py 生成，写入 data/recipe_plain_ai.json
  （纯文本入 git，便于真人逐条审校/修改；运行期只读，不动 shiyang.db）
- 自定义方子：按需实时生成，进程内缓存（相同药材组合不重复调用）
"""
import json
import os
import re
from pathlib import Path

import requests

PLAIN_JSON = Path(__file__).resolve().parents[3] / "data" / "recipe_plain_ai.json"

AI_BASE_URL = os.environ.get("SHIYANG_AI_BASE_URL") or "http://127.0.0.1:7863/v1"
AI_MODEL = os.environ.get("SHIYANG_AI_MODEL") or "deepseek-v4-flash"
AI_TIMEOUT = 45
CUSTOM_AI_TIMEOUT = (2, 6)

# 红线词：命中即判生成失败（不做替换，避免改坏语义后仍上线）
BANNED = ("治疗", "疗效", "治愈", "根治", "抗癌", "防癌", "药到病除", "包治", "特效", "处方")

PLAIN_PROMPT = """你是「食养有据」平台的科普编辑，任务是把一个茶饮/药膳方的传统功效翻译成普通人一看就懂的大白话。
读者是完全不懂中医的普通人（比如大学生、上班族、家里老人）。

只能依据用户给出的资料改写，资料里没有的功效一律不写，不要联想、不要补充。

写作要求：
1. 把中医术语换成日常说法，例如：清热→帮身体"降降火"；补气→适合容易累、没精神的时候；
   健脾→帮肠胃消化；润肺→嗓子干、干咳时比较舒服；安神→有助于放松、睡得踏实；
   祛湿→适合身体沉重、舌苔厚腻的时候。可以保留一个括号注明原术语，如"降降火（清热）"。
2. 语气用"传统上认为""可能有助于""比较适合"，不要下结论。
3. 绝对不能出现：治疗、疗效、治愈、根治、抗癌、防癌、药到病除、包治、特效、处方；
   不提任何疾病名称作为功效对象；不提数字评分或实验数据。
4. 禁忌部分必须如实保留资料里的禁忌信息，改成大白话，不能弱化。

严格输出 JSON 对象，不要输出任何其他文字：
{
  "headline": "一句话说清这是一杯/一碗什么、传统上用来做什么（不超过30字）",
  "suits": "什么样的人、什么时候喝比较合适（不超过60字）",
  "caution": "哪些人要注意或别喝（不超过60字，资料没写禁忌就写'资料未注明禁忌，身体有特殊情况先问医生'）",
  "ingredients": [{"name": "配料名", "role": "这味料在方子里起什么作用，大白话（不超过25字）"}]
}
ingredients 按资料里的配料顺序逐一列出，食材（非药材）也要写，例如"冰糖：调味，让口感更好"。"""


# ---------------- 输入组装 ----------------

def build_recipe_input(recipe: dict, materials: list[dict]) -> dict:
    """已有方子 → 模型输入（只放传统资料字段，不放入血概率等预测值）"""
    mats = []
    for m in materials:
        item = {"名称": m.get("name"), "类别": "药食同源" if m.get("material_type") == "herb" else "食材"}
        if m.get("grams"):
            item["克重"] = m["grams"]
        tradition = "；".join(x for x in (
            m.get("nature") and f"性{m['nature']}",
            m.get("flavor") and f"味{m['flavor']}",
            m.get("functions")) if x)
        if tradition:
            item["传统功效"] = tradition
        mats.append(item)
    return {
        "方名": recipe.get("name"),
        "类型": recipe.get("type"),
        "传统定位": recipe.get("oneliner"),
        "说明": recipe.get("description"),
        "配料": mats,
        "适宜体质": recipe.get("constitutions_suitable"),
        "不宜体质": recipe.get("constitutions_unsuitable"),
        "适合人群": recipe.get("population"),
        "禁忌": recipe.get("contraindication"),
    }


def build_custom_input(herbs: list[dict]) -> dict:
    """自定义方子 → 模型输入（性味/功效来自 herb_service 已查到的字段）"""
    mats = []
    for h in herbs:
        name = (h.get("name") or "").strip()
        if not name:
            continue
        item = {"名称": name}
        if h.get("grams"):
            item["克重"] = h["grams"]
        if h.get("properties"):
            item["性味"] = str(h["properties"])[:80]
        if h.get("functions"):
            item["传统功效"] = str(h["functions"])[:200]
        mats.append(item)
    return {"类型": "用户自配方子", "配料": mats,
            "禁忌": "资料未提供，请提醒孕妇、慢病及正在服药人群先咨询医生"}


# ---------------- 模型调用与校验 ----------------

def _call_model(payload: dict, api_key: str | None = None, *, timeout=AI_TIMEOUT) -> str:
    key = (api_key or "").strip() or os.environ.get("SHIYANG_AI_KEY") or "zerogate"
    r = requests.post(
        f"{AI_BASE_URL.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": AI_MODEL,
            "messages": [
                {"role": "system", "content": PLAIN_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=1)},
            ],
            "temperature": 0.3,
            "stream": False,
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return (r.json()["choices"][0]["message"]["content"] or "").strip()


def parse_and_validate(raw: str, material_names: list[str]) -> dict:
    """解析模型输出并校验；不合格抛 ValueError（调用方决定重试或放弃）。

    - 结构：headline/suits/caution 必须是非空字符串，ingredients 为列表
    - 红线词：任一字段命中 BANNED 即判失败
    - 防幻觉：ingredients 只保留输入里真实存在的配料名
    """
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).rstrip("`").strip()
    if "{" in text:
        text = text[text.find("{"): text.rfind("}") + 1]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("输出不是对象")
    out = {}
    for k in ("headline", "suits", "caution"):
        v = data.get(k)
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"缺少字段 {k}")
        out[k] = v.strip()
    names = set(material_names)
    ings = []
    for it in data.get("ingredients") or []:
        if isinstance(it, dict) and it.get("name") in names and isinstance(it.get("role"), str):
            ings.append({"name": it["name"], "role": it["role"].strip()})
    out["ingredients"] = ings
    blob = json.dumps(out, ensure_ascii=False)
    hit = [w for w in BANNED if w in blob]
    if hit:
        raise ValueError(f"命中红线词 {hit}")
    return out


def generate(payload: dict, api_key: str | None = None, retries: int = 1, *, timeout=AI_TIMEOUT) -> dict:
    """调模型生成白话解读，校验失败重试一次。返回解读 dict（不含元数据）。"""
    names = [m["名称"] for m in payload.get("配料", [])]
    last = None
    for _ in range(retries + 1):
        try:
            return parse_and_validate(_call_model(payload, api_key, timeout=timeout), names)
        except Exception as e:  # 网络/解析/红线都走重试
            last = e
    raise RuntimeError(f"白话解读生成失败：{last}")


# ---------------- 读取（已有方子） ----------------

_cache: dict | None = None
_cache_mtime: float | None = None


def _load_all() -> dict:
    """读 data/recipe_plain_ai.json；文件变化时自动重载（便于审校后热更新）"""
    global _cache, _cache_mtime
    if not PLAIN_JSON.exists():
        return {}
    mtime = PLAIN_JSON.stat().st_mtime
    if _cache is None or mtime != _cache_mtime:
        try:
            _cache = json.loads(PLAIN_JSON.read_text(encoding="utf-8")).get("items", {})
        except (json.JSONDecodeError, OSError):
            _cache = {}
        _cache_mtime = mtime
    return _cache


def get_recipe_plain(recipe_id: int) -> dict | None:
    item = _load_all().get(str(recipe_id))
    if not item:
        return None
    return {
        **item["content"],
        "source": "ai",
        "model": item.get("model"),
        "generated_at": item.get("generated_at"),
        "reviewed": bool(item.get("reviewed")),
    }


# ---------------- 自定义方子（实时生成 + 进程内缓存） ----------------

_custom_cache: dict[str, dict] = {}
_CUSTOM_CACHE_MAX = 200

_TRADITIONAL_ROLES = (
    (("健脾", "消食", "strengthen spleen", "promote digestion"), "在传统记载里多用于帮助消化"),
    (("deficiency syndrome of the spleen",), "传统资料有关于脾胃偏弱的记载"),
    (("清热", "疏散风热", "clear heat", "dispel wind-heat"), "传统上用于清热，俗称清火"),
    (("补气", "益气", "元气", "tonify qi", "replenish qi", "reinforce the vital energy"), "传统上用于补气，也就是常说的补元气"),
    (("养阴", "滋阴", "益精", "nourish yin"), "属于传统资料里常见的滋养用料"),
    (("润肺", "润燥", "生津", "moisten lung", "engender fluid"), "传统上用于润燥、生津"),
    (("理气", "行气", "regulate qi", "move qi"), "传统上用于理气"),
    (("安神", "宁心", "calm the spirit"), "传统上用于宁心安神"),
    (("固精", "缩尿", "涩精", "astringe"), "传统上用于收涩，有收敛的意思"),
    (("frequent urination",), "传统资料有关于小便频繁的记载"),
)


def custom_reference_only() -> bool:
    return os.environ.get("SHIYANG_CUSTOM_PLAIN_REFERENCE_ONLY") == "1"


def custom_reference(details: list[dict]) -> dict:
    """按已核对的单味资料整理。仅释义常见术语，不推断整方效果。"""
    ingredients = {}
    for detail in details:
        name = detail.get("name_cn") or detail.get("herb_name")
        if not name:
            continue
        function = (detail.get("functions_cn") if detail.get("functions_cn_source") == "curated"
                    else detail.get("function_en"))
        function = function.lower() if isinstance(function, str) else ""
        role = next((wording for terms, wording in _TRADITIONAL_ROLES
                     if any(term in function for term in terms)), "现有资料里暂缺适合简述的传统用途")
        ingredients[name] = {"name": name, "role": role}

    return {
        "source": "reference",
        "model": None,
        "reviewed": False,
        "headline": "这份方子的配料资料" if ingredients else "暂未查到可整理的配料资料",
        "suits": "下方是查到的单味资料。整份方子是否适合你，还要结合用量和个人情况判断。",
        "caution": "未收录的配料请先核对名称。怀孕、正在用药或有慢病的人，使用前请先咨询专业人员。",
        "ingredients": list(ingredients.values()),
    }


def custom_plain(herbs: list[dict], api_key: str | None = None) -> dict:
    payload = build_custom_input(herbs)
    if not payload["配料"]:
        raise ValueError("没有可解读的药材")
    key = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if key in _custom_cache:
        return _custom_cache[key]
    content = generate(payload, api_key, retries=0, timeout=CUSTOM_AI_TIMEOUT)
    result = {**content, "source": "ai", "model": AI_MODEL, "reviewed": False}
    if len(_custom_cache) >= _CUSTOM_CACHE_MAX:
        _custom_cache.pop(next(iter(_custom_cache)))
    _custom_cache[key] = result
    return result
