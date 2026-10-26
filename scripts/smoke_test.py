# -*- coding: utf-8 -*-
"""API 冒烟测试：覆盖全部公开接口 + 用户系统主要路径。用法: python -X utf8 scripts/smoke_test.py"""
import json, urllib.request, urllib.error, urllib.parse, base64, random, string

import os
BASE = os.environ.get("SMOKE_BASE", "http://127.0.0.1:8100") + "/api/v1"
TOKEN = None
results = []

def req(method, path, body=None, auth=False, raw=False):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if auth and TOKEN:
        r.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            payload = resp.read().decode("utf-8", "replace")
            if raw:
                return resp.status, payload
            return resp.status, json.loads(payload)
    except urllib.error.HTTPError as e:
        payload = e.read().decode("utf-8", "replace")
        if raw:
            return e.code, payload
        try:
            return e.code, json.loads(payload)
        except Exception:
            return e.code, payload
    except Exception as e:
        return -1, str(e)

def check(name, cond, extra=""):
    results.append((name, bool(cond), str(extra)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + ("" if cond else f"  <-- {extra}"))

def pick(d, *keys):
    for k in keys:
        if isinstance(d, dict) and k in d:
            d = d[k]
        else:
            return None
    return d

# ---------- 系统 ----------
s, j = req("GET", "/health")
check("health", s == 200 and pick(j, "data", "status") == "up", f"code={s}")

s, j = req("GET", "/stats")
check("stats", s == 200 and (pick(j, "data", "stats", "recipe") or 0) > 0, f"code={s} stats={pick(j,'data','stats')}")

# ---------- 体质 ----------
s, j = req("GET", "/constitution/questionnaire")
items = pick(j, "data", "items") or {}
check("questionnaire", s == 200 and isinstance(items, dict) and len(items) >= 8, f"code={s} n={len(items)}")
print("   维度:", list(items.keys()))

answers = {code: [4.0] * len(qs) for code, qs in items.items()}
s, j = req("POST", "/constitution/submit", {"answers": answers})
check("submit 偏颇答案", s == 200 and pick(j, "data", "judged") is not None, f"code={s} resp={str(j)[:200]}")
if s == 200:
    mc = pick(j, "data", "main_constitution") or {}
    print("   main:", mc.get("name"), "推荐数:", len(pick(j, "data", "recommendations") or []))

answers2 = {code: [1.0] * len(qs) for code, qs in items.items()}
s, j = req("POST", "/constitution/submit", {"answers": answers2})
check("submit 平和答案", s == 200, f"code={s}")
if s == 200:
    mc = pick(j, "data", "main_constitution") or {}
    print("   main(全1分):", mc.get("name"), "pinghe:", pick(j, "data", "judged", "results", "pinghe", "result"))

s, j = req("POST", "/constitution/submit", {"answers": {"nonsense": [1, 2]}})
check("submit 非法维度→400", s == 400, f"code={s} resp={str(j)[:120]}")
s, j = req("POST", "/constitution/submit", {"answers": {}})
check("submit 空答案→400", s == 400, f"code={s} resp={str(j)[:120]}")

s, j = req("GET", "/constitution/pinghe")
check("constitution/pinghe", s == 200 and pick(j, "data", "name") is not None, f"code={s}")
s, j = req("GET", "/constitution/nonexistent_xyz")
check("constitution 未知code→404", s == 404, f"code={s}")

# ---------- 方子库 ----------
s, j = req("GET", "/recipes?page=1&size=5")
data = pick(j, "data") or {}
check("recipes 列表", s == 200 and len(data.get("items") or []) > 0, f"code={s}")
total = data.get("total", 0)
first = (data.get("items") or [{}])[0]
first_id = first.get("id")
print(f"   total={total} 首条:", json.dumps(first, ensure_ascii=False)[:160])

s, j = req("GET", "/recipes?page=2&size=5")
check("recipes 翻页", s == 200 and len(pick(j, "data", "items") or []) > 0, f"code={s}")

s, j = req("GET", "/recipes?type=%E8%8C%B6%E9%A5%AE")
titems = pick(j, "data", "items") or []
check("recipes type过滤", s == 200 and all(r["type"] == "茶饮" for r in titems), f"code={s}")
print("   type=茶饮 total:", pick(j, "data", "total"))

s, j = req("GET", "/recipes?q=%E6%9E%B8%E6%9D%9E")
check("recipes q搜索", s == 200, f"code={s}")
print("   q=枸杞 total:", pick(j, "data", "total"))

s, j = req("GET", "/recipes?size=100")
allitems = pick(j, "data", "items") or []
scene0 = next((sc for r in allitems for sc in (r.get("scenes") or [])), None)
const0 = next((c for r in allitems for c in (r.get("constitutions_suitable") or [])), None)
if scene0:
    s, j = req("GET", "/recipes?scene=" + urllib.parse.quote(scene0))
    check(f"recipes scene过滤({scene0})", s == 200 and (pick(j, "data", "total") or 0) > 0,
          f"code={s} total={pick(j,'data','total')}")
if const0:
    s, j = req("GET", "/recipes?constitution=" + urllib.parse.quote(const0))
    check(f"recipes constitution过滤({const0})", s == 200 and (pick(j, "data", "total") or 0) > 0,
          f"code={s} total={pick(j,'data','total')}")

# 翻页边界：size=100 page 很大
s, j = req("GET", "/recipes?page=999&size=5")
check("recipes 越界页", s == 200 and (pick(j, "data", "items") or []) == [], f"code={s} n={len(pick(j,'data','items') or [])}")

# 分页+过滤组合是否自洽：total 应等于全量过滤后的数量
s, j = req("GET", "/recipes?scene=" + urllib.parse.quote(scene0 or "护嗓润喉"))
t_all = pick(j, "data", "total")
s, j = req("GET", "/recipes?scene=" + urllib.parse.quote(scene0 or "护嗓润喉") + "&page=1&size=2")
check("recipes 过滤+分页一致", s == 200 and len(pick(j, "data", "items") or []) == 2, f"code={s} total={t_all}")

if first_id:
    s, j = req("GET", f"/recipes/{first_id}")
    check("recipe 详情", s == 200 and pick(j, "data", "name") is not None, f"code={s}")
    print(f"   id={first_id} 配料数={len(pick(j,'data','materials') or [])} analysis={'有' if pick(j,'data','analysis') else '无'}")
    s, j = req("GET", "/recipes/99999")
    check("recipe 不存在→404", s == 404, f"code={s}")

other = next((r["id"] for r in allitems if r["id"] != first_id and r.get("analysis_ready")), None)
s, j = req("GET", f"/recipes/compare?a={first_id}&b={first_id}")
check("compare 同一方→400", s == 400, f"code={s}")
if other:
    s, j = req("GET", f"/recipes/compare?a={first_id}&b={other}")
    check("compare 两方", s == 200 and pick(j, "data") is not None, f"code={s} resp={str(j)[:150]}")
s, j = req("GET", "/recipes/compare?a=99999&b=99998")
check("compare 不存在→404", s == 404, f"code={s}")

# ---------- 茶罐 ----------
s, j = req("GET", "/pantry/materials")
mitems = pick(j, "data", "items") or []
check("pantry/materials", s == 200 and (pick(j, "data", "total") or 0) > 0, f"code={s}")
mats3 = [m["name"] for m in mitems[:3]]
print("   前3配料:", mats3)
s, j = req("POST", "/pantry/match", {"owned": mats3})
check("pantry/match", s == 200, f"code={s} resp={str(j)[:150]}")
s, j = req("POST", "/pantry/match", {"owned": ["不存在的食材xyz"]})
check("pantry/match 未知食材", s == 200, f"code={s} resp={str(j)[:150]}")
s, j = req("POST", "/pantry/match", {"owned": mats3, "constitution": "气虚"})
check("pantry/match 带体质", s == 200, f"code={s}")

# ---------- 安全滤镜 ----------
s, j = req("GET", "/safety/profiles")
plist = pick(j, "data", "items") or []
check("safety/profiles", s == 200 and len(plist) > 0, f"code={s}")
pkeys = [p.get("key") or p.get("id") or p.get("name") for p in plist]
print("   人群档案keys:", pkeys)
if first_id and pkeys:
    # profile 参数要取 code 类字段（diabetes 等），中文名会被当未知档案 404
    p0 = pkeys[0]
    pcodes = [p.get("code") for p in plist if p.get("code")] or pkeys
    p0 = pcodes[0]
    s, j = req("GET", f"/safety/check/{first_id}?profile={urllib.parse.quote(str(p0))}")
    check(f"safety/check({p0})", s == 200, f"code={s} resp={str(j)[:150]}")
    s, j = req("GET", f"/safety/check/{first_id}?profile=no_such_profile")
    check("safety/check 未知profile→404", s == 404, f"code={s}")
    ids = [r["id"] for r in allitems[:10]]
    s, j = req("POST", "/safety/check-batch", {"recipe_ids": ids, "profile": p0})
    check("safety/check-batch", s == 200, f"code={s} resp={str(j)[:120]}")
    s, j = req("POST", "/safety/check-batch", {"recipe_ids": ids, "profile": "nope"})
    check("safety/check-batch 未知profile→404", s == 404, f"code={s}")

# ---------- 证据 / 可解释 ----------
s, j = req("GET", "/evidence/levels")
check("evidence/levels", s == 200, f"code={s}")
if first_id:
    s, j = req("GET", f"/evidence/recipe/{first_id}")
    check("evidence/recipe", s == 200, f"code={s} resp={str(j)[:150]}")
    s, j = req("GET", f"/explain/recipe/{first_id}")
    check("explain/recipe", s == 200, f"code={s} resp={str(j)[:120]}")
s, j = req("GET", "/explain/compound?name=%E6%9F%9A%E7%9A%AE%E7%B4%A0")
check("explain/compound(柚皮素)", s == 200, f"code={s} resp={str(j)[:120]}")
s, j = req("GET", "/explain/compound?name=zzz_not_exist")
check("explain/compound 未知→404", s == 404, f"code={s}")

# ---------- 药材 / 成分 ----------
s, j = req("GET", "/herbs")
check("herbs 全量", s == 200 and (pick(j, "data", "total") or 0) > 0, f"code={s}")
print("   herbs total:", pick(j, "data", "total"))
s, j = req("GET", "/herbs?q=%E6%9E%B8%E6%9D%9E")
check("herbs q=枸杞", s == 200 and len(pick(j, "data", "items") or []) > 0, f"code={s}")
s, j = req("GET", "/compounds?min_prob=0.8&limit=10")
citems = pick(j, "data", "items") or []
check("compounds min_prob=0.8", s == 200 and len(citems) <= 10, f"code={s} n={len(citems)}")
s, j = req("GET", "/compounds?min_prob=2")
check("compounds min_prob越界钳制", s == 200, f"code={s}")
# min_prob 一致性：items 的 prob 应都 >= min_prob
if citems:
    bad = [c for c in citems if (c.get("prob_cctcm") or 0) < 0.8]
    check("compounds 过滤一致性", not bad, f"违规: {bad[:2]}")

# ---------- 暴露量 / 网络图 ----------
if first_id:
    s, j = req("GET", f"/recipes/{first_id}/exposure")
    exp_items = pick(j, "data", "items") or []
    absorbed = [e for e in exp_items if "absorbed_mg_max" in e]
    check("exposure", s == 200, f"code={s} resp={str(j)[:150]}")
    check("exposure 含吸收期望(摄入×入血概率)", bool(absorbed),
          f"n_absorbed={len(absorbed)} n_items={len(exp_items)}")
    bad_math = [e for e in absorbed
                if abs(e["absorbed_mg_max"] - e["est_mg_max"] * e["prob_cctcm"]) >= 0.05]
    check("exposure 吸收期望数值自洽", not bad_math, f"违规: {bad_math[:2]}")
    s, j = req("GET", f"/recipes/{first_id}/network")
    nodes = pick(j, "data", "nodes") or []
    check("network", s == 200 and len(nodes) > 0, f"code={s}")
    check("network 注明仅人类靶点", "人类蛋白" in (pick(j, "data", "note") or ""),
          f"note={pick(j,'data','note')}")
    s, j = req("GET", f"/recipes/{first_id}/network?max_compounds=2&max_targets=3")
    nodes2 = pick(j, "data", "nodes") or []
    check("network 限额", s == 200 and len(nodes2) <= 6, f"code={s} nodes={len(nodes2)}")
    s, j = req("GET", "/recipes/99999/network")
    check("network 不存在→404", s == 404, f"code={s}")

    # 通路富集（GO BP + KEGG，预生成缓存）
    s, j = req("GET", f"/recipes/{first_id}/pathways")
    pw = pick(j, "data") or {}
    check("pathways", s == 200 and pw.get("status") in ("ok", "insufficient", "offline"),
          f"code={s} status={pw.get('status')}")
    if pw.get("status") == "ok":
        check("pathways 有 GO 中文词条", any(p.get("term_zh") for p in (pw.get("pathways") or [])),
              f"pathways={len(pw.get('pathways') or [])}")
        bad = [p for p in (pw.get("pathways_kegg") or [])
               if any(b in (p.get("term") or "").lower()
                      for b in ("cancer", "carcinogenesis", "hepatitis", "infection", "disease"))]
        check("pathways KEGG 无疾病类词条", not bad, f"违规: {[b.get('term') for b in bad][:2]}")
    check("pathways 注明生物信息学推断", "生物信息学推断" in (pw.get("note") or ""),
          f"note={str(pw.get('note'))[:60]}")
    s, j = req("GET", "/recipes/99999/pathways")
    check("pathways 不存在→404", s == 404, f"code={s}")

# ---------- 节气 ----------
s, j = req("GET", "/term/current")
check("term/current", s == 200 and pick(j, "data", "current", "name") is not None, f"code={s}")
print("   当前节气:", json.dumps(pick(j, "data", "current"), ensure_ascii=False)[:140])
s, j = req("GET", "/term/current?count=0")
check("term/current count=0 钳制", s == 200, f"code={s}")

# ---------- 用户系统 ----------
uname = "t_" + "".join(random.choices(string.ascii_lowercase, k=8))
s, j = req("POST", "/auth/register", {"username": uname, "password": "test1234", "nickname": "测试员"})
check("register", s == 200 and pick(j, "data", "token"), f"code={s} resp={str(j)[:150]}")
TOKEN = pick(j, "data", "token")
s, j = req("POST", "/auth/register", {"username": uname, "password": "whatever123"})
check("register 重复→400", s == 400, f"code={s} resp={str(j)[:100]}")
s, j = req("POST", "/auth/register", {"username": "a", "password": "x"})
check("register 短用户名→400", s == 400, f"code={s} resp={str(j)[:100]}")
s, j = req("POST", "/auth/login", {"username": uname, "password": "wrongpw"})
check("login 错密码→400", s == 400, f"code={s}")
s, j = req("POST", "/auth/login", {"username": uname.upper(), "password": "test1234"})
print(f"   大小写敏感登录: code={s}（仅记录）")
s, j = req("POST", "/auth/login", {"username": uname, "password": "test1234"})
check("login", s == 200 and pick(j, "data", "token"), f"code={s}")

s, j = req("GET", "/me", auth=True)
check("me", s == 200 and pick(j, "data", "username") == uname, f"code={s}")
s, j = req("GET", "/me")
check("me 无token→401", s == 401, f"code={s}")
fake = base64.b64encode(b'{"uid": 1}').decode()
s, j = req("GET", "/me", auth=False)
r = urllib.request.Request(BASE + "/me")
r.add_header("Authorization", f"Bearer {fake}")
try:
    with urllib.request.urlopen(r, timeout=10) as resp:
        code = resp.status
except urllib.error.HTTPError as e:
    code = e.code
check("me 伪造token→401", code == 401, f"code={code}")

s, j = req("POST", "/constitution/records", {"judged": {"a": 1}, "transformed": {"a": 1}, "answers": {"a": [1]}}, auth=True)
check("保存体质档案", s == 200, f"code={s} resp={str(j)[:100]}")
s, j = req("GET", "/constitution/records", auth=True)
check("读取体质档案", s == 200 and len(pick(j, "data") or []) > 0, f"code={s}")

s, j = req("POST", "/family/members", {"name": "老妈", "relation": "母亲", "color": "#ff8800"}, auth=True)
check("添加家庭成员", s == 200, f"code={s} resp={str(j)[:120]}")
mid = pick(j, "data", "id")
s, j = req("GET", "/family/members", auth=True)
check("家庭成员列表", s == 200 and len(pick(j, "data") or []) > 0, f"code={s}")
if mid:
    s, j = req("DELETE", f"/family/members/{mid}", auth=True)
    check("删除家庭成员", s == 200, f"code={s}")
    s, j = req("DELETE", f"/family/members/{mid}", auth=True)
    check("重复删除成员→404", s == 404, f"code={s}")

# ---------- 收藏 ----------
if first_id:
    s, j = req("POST", f"/favorites/{first_id}", auth=True)
    check("收藏方子", s == 200, f"code={s}")
    s, j = req("POST", f"/favorites/{first_id}", auth=True)
    check("重复收藏", s == 200, f"code={s} resp={str(j)[:100]}")
    s, j = req("GET", "/favorites", auth=True)
    favs = pick(j, "data") or []
    check("收藏列表", s == 200 and any(f["id"] == first_id for f in favs), f"code={s} n={len(favs)}")
    s, j = req("DELETE", f"/favorites/{first_id}", auth=True)
    check("取消收藏", s == 200, f"code={s}")
    s, j = req("GET", "/favorites", auth=True)
    check("收藏列表已清", s == 200 and not any(f["id"] == first_id for f in (pick(j, "data") or [])), f"code={s}")
    s, j = req("POST", "/favorites/99999", auth=True)
    print(f"   收藏不存在方子: code={s} resp={str(j)[:100]}（仅记录）")

# ---------- 打卡 ----------
if first_id:
    s, j = req("POST", f"/checkins/{first_id}", auth=True)
    check("打卡", s == 200, f"code={s} resp={str(j)[:120]}")
    s, j = req("POST", f"/checkins/{first_id}", auth=True)
    check("重复打卡", s == 200, f"code={s} resp={str(j)[:150]}")
    s, j = req("GET", "/checkins", auth=True)
    crecs = pick(j, "data", "records") or []
    check("打卡列表", s == 200 and len(crecs) > 0, f"code={s} n={len(crecs)}")
    if crecs:
        print("   打卡样例:", json.dumps(crecs[0], ensure_ascii=False)[:160])
    s, j = req("DELETE", f"/checkins/{first_id}", auth=True)
    check("撤销打卡", s == 200, f"code={s}")
    s, j = req("DELETE", f"/checkins/{first_id}", auth=True)
    print(f"   重复撤销打卡: code={s}（仅记录，期望幂等或404）")

s, j = req("GET", "/report/cycle?days=21", auth=True)
check("report/cycle", s == 200, f"code={s} resp={str(j)[:200]}")
s, j = req("GET", "/report/cycle?days=999", auth=True)
check("report/cycle days钳制", s == 200, f"code={s}")

# ---------- AI 解读（SSE） ----------
if first_id:
    s, raw = req("GET", f"/recipes/{first_id}/ai-report", raw=True)
    check("ai-report pregen回放", s == 200 and "data:" in (raw or ""), f"code={s} head={str(raw)[:80]}")
    if s == 200:
        print(f"   SSE delta数={raw.count(chr(34)+'delta'+chr(34))} DONE={'[DONE]' in raw} 字节={len(raw)}")
    s, raw = req("GET", "/recipes/99999/ai-report", raw=True)
    check("ai-report 不存在→404", s == 404, f"code={s}")

# ---------- 开放数据 ----------
s, j = req("GET", "/open")
check("open 索引", s == 200, f"code={s} resp={str(j)[:120]}")
for p in ("/open/catalog", "/open/herbs", "/open/compounds", "/open/constitutions",
          "/open/stats", "/open/snapshot"):
    s, j = req("GET", p)
    check(f"open {p.split('/')[-1]}", s == 200, f"code={s}")
s, j = req("GET", "/open/compounds/%E6%9F%9A%E7%9A%AE%E7%B4%A0/targets")
tn = pick(j, "data", "targets") or []
sp = {t.get("target_species") for t in tn}
check("open/compounds/柚皮素/targets 默认仅人类", s == 200 and tn and sp == {"Homo sapiens"},
      f"code={s} n={len(tn)} species={sp}")
s, j = req("GET", "/open/compounds/%E6%9F%9A%E7%9A%AE%E7%B4%A0/targets?species=all")
tn2 = pick(j, "data", "targets") or []
sp2 = {t.get("target_species") for t in tn2}
check("open/compounds/柚皮素/targets species=all 含非人类", s == 200 and len(sp2) > 1,
      f"code={s} n={len(tn2)} species_n={len(sp2)}")

# ---------- 汇总 ----------
fails = [r for r in results if not r[1]]
print(f"\n===== 冒烟汇总: {len(results) - len(fails)}/{len(results)} 通过 =====")
for name, _, extra in fails:
    print(f"  FAIL: {name}  {extra}")
