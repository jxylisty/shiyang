# -*- coding: utf-8 -*-
"""
构建 shiyang 数据库：
1) 从哮喘库只读抽取 73 方涉及的药材/化合物/靶点/关联数据
2) 建 food（普通食材）、recipe、rel_recipe_material、constitution、constitution_food_ref 表
输出：data/shiyang.db
用法：python -X utf8 build_db.py
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT.parent / "my-asthma-system" / "asthma-core" / "data" / "asthma_v2.db"
OUT = ROOT / "data" / "shiyang.db"
CATALOG = json.loads((ROOT / "data" / "food_homology_catalog.json").read_text(encoding="utf-8"))
RECIPES = json.loads((ROOT / "data" / "recipes_v0.1.json").read_text(encoding="utf-8"))["recipes"]
CONSTITUTION = json.loads((ROOT / "data" / "recipes_raw" / "constitution.json").read_text(encoding="utf-8"))

if OUT.exists():
    OUT.unlink()

src = sqlite3.connect(f"file:{SRC.as_posix()}?mode=ro", uri=True)
dst = sqlite3.connect(OUT)
dst.execute("PRAGMA journal_mode=WAL")

# ---------- 1. 抽取药材/化合物/靶点 ----------
# 配料中 kind=药食同源 且 analysis_ready 的名字 → 现有库 herb.name
herb_names = set()
for r in RECIPES:
    for m in r["materials"]:
        if m.get("analysis_ready"):
            herb_names.add(m["name"])
herb_names |= {"花椒", "橘红"}  # 目录内、库内有条目（即使 0 化合物）一并带走

placeholders = ",".join("?" * len(herb_names))
herbs = src.execute(
    f"SELECT id,name,pinyin,alias,latin_name,category,functions,nature,flavor,meridians,"
    f"medicinal_part,dosage,toxicity,contraindication,compound_count FROM herb WHERE name IN ({placeholders})",
    tuple(herb_names)).fetchall()
herb_ids = [h[0] for h in herbs]
name_by_id = {h[0]: h[1] for h in herbs}
print(f"药材抽取: {len(herbs)} 味")

hp = ",".join("?" * len(herb_ids))
rel_hc = src.execute(f"SELECT herb_id,compound_id FROM rel_herb_compound WHERE herb_id IN ({hp})", tuple(herb_ids)).fetchall()
compounds = src.execute(
    f"SELECT DISTINCT c.id,c.name,c.smiles,c.mw,c.logp,c.prob_cctcm,c.prob_herb,"
    f"c.radar_anti_inflammatory,c.radar_immune_regulation,c.radar_airway_repair,c.target_count "
    f"FROM compound c JOIN rel_herb_compound r ON r.compound_id=c.id WHERE r.herb_id IN ({hp})",
    tuple(herb_ids)).fetchall()
comp_ids = [c[0] for c in compounds]
print(f"化合物抽取: {len(compounds)} 个 | 药材-化合物关联: {len(rel_hc)} 条")

cp = ",".join("?" * len(comp_ids))
rel_ct = src.execute(
    f"SELECT compound_id,target_gene,activity_type,activity_value,activity_unit,reference,source_db "
    f"FROM rel_compound_target WHERE compound_id IN ({cp})", tuple(comp_ids)).fetchall()
targets = src.execute(
    f"SELECT DISTINCT t.gene,t.target_type,t.species FROM target t "
    f"JOIN rel_compound_target r ON r.target_gene=t.gene WHERE r.compound_id IN ({cp})", tuple(comp_ids)).fetchall()
print(f"靶点抽取: {len(targets)} 个 | 化合物-靶点关联: {len(rel_ct)} 条")

dst.executescript("""
CREATE TABLE herb (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, pinyin TEXT, alias TEXT, latin_name TEXT,
    category TEXT, functions TEXT, nature TEXT, flavor TEXT, meridians TEXT,
    medicinal_part TEXT, dosage TEXT, toxicity TEXT, contraindication TEXT,
    compound_count INTEGER, is_food_homology INTEGER DEFAULT 1, food_catalog_batch INTEGER
);
CREATE INDEX idx_herb_name ON herb(name);
CREATE TABLE compound (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, smiles TEXT, mw REAL, logp REAL,
    prob_cctcm REAL, prob_herb REAL,
    radar_anti_inflammatory REAL, radar_immune_regulation REAL, radar_airway_repair REAL,
    target_count INTEGER
);
CREATE INDEX idx_compound_name ON compound(name);
CREATE INDEX idx_compound_prob ON compound(prob_cctcm);
CREATE TABLE target (
    gene TEXT PRIMARY KEY, target_type TEXT, species TEXT
);
CREATE TABLE rel_herb_compound (
    id INTEGER PRIMARY KEY AUTOINCREMENT, herb_id TEXT REFERENCES herb(id), compound_id TEXT REFERENCES compound(id),
    UNIQUE(herb_id, compound_id)
);
CREATE TABLE rel_compound_target (
    id INTEGER PRIMARY KEY AUTOINCREMENT, compound_id TEXT REFERENCES compound(id), target_gene TEXT REFERENCES target(gene),
    activity_type TEXT, activity_value REAL, activity_unit TEXT, reference TEXT, source_db TEXT
);
CREATE INDEX idx_rct_compound ON rel_compound_target(compound_id);
CREATE INDEX idx_rct_target ON rel_compound_target(target_gene);
""")

# 目录批次标注
batch_by_alias = {}
for it in CATALOG["items"]:
    batch_by_alias[it["name"]] = it["batch"]
    for a in it["aliases"]:
        batch_by_alias.setdefault(a, it["batch"])

dst.executemany(
    "INSERT INTO herb VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)",
    [(*h, batch_by_alias.get(h[1])) for h in herbs])
dst.executemany("INSERT INTO compound VALUES (?,?,?,?,?,?,?,?,?,?,?)", compounds)
dst.executemany("INSERT INTO target VALUES (?,?,?)", targets)
dst.executemany("INSERT INTO rel_herb_compound(herb_id,compound_id) VALUES (?,?)", rel_hc)
dst.executemany("INSERT INTO rel_compound_target(compound_id,target_gene,activity_type,activity_value,activity_unit,reference,source_db) VALUES (?,?,?,?,?,?,?)", rel_ct)

# ---------- 2. 普通食材表 ----------
dst.execute("""
CREATE TABLE food (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    category TEXT,          -- 水果/谷物/蔬菜/肉禽/水产/调味/其他
    nature TEXT, flavor TEXT, functions TEXT,
    contraindication TEXT,
    nutrient_json TEXT,     -- 预留：中国食物成分表营养素
    note TEXT
)""")
FOOD_META = {  # 简要性味功效，正式版以《中华本草》/食材图谱核对补充
    "雪梨": ("水果", "凉", "甘、微酸", "生津润燥、清热化痰", "脾胃虚寒便溏者少食"),
    "鸭梨": ("水果", "凉", "甘、微酸", "生津润燥", "脾胃虚寒者少食"),
    "马蹄": ("蔬菜", "寒", "甘", "清热生津、消食", "脾胃虚寒者不宜多食"),
    "粳米": ("谷物", "平", "甘", "补中益气、健脾和胃", None),
    "小米": ("谷物", "凉", "甘、咸", "健脾和胃、安眠", None),
    "糯米": ("谷物", "温", "甘", "补中益气", "消化弱者少食"),
    "冰糖": ("调味", "平", "甘", "润肺生津调味", "糖尿病人群控制用量"),
    "白糖": ("调味", "平", "甘", "调味", "糖尿病人群控制用量"),
    "红糖": ("调味", "温", "甘", "温中活血调味", "糖尿病人群控制用量"),
    "牛奶": ("其他", "平", "甘", "滋阴润燥", "乳糖不耐者慎用"),
    "鸡蛋": ("其他", "平", "甘", "滋阴润燥养血", "过敏者禁用"),
    "猪瘦肉": ("肉禽", "平", "甘、咸", "滋阴润燥", "高血脂适量"),
    "排骨": ("肉禽", "平", "甘、咸", "益气滋阴", "高血脂适量"),
    "猪骨": ("肉禽", "平", "甘、咸", "益气滋阴", "高尿酸少喝汤"),
    "猪脊骨": ("肉禽", "平", "甘、咸", "益气滋阴", "高尿酸少喝汤"),
    "猪肚": ("肉禽", "温", "甘", "健脾养胃", "高胆固醇适量"),
    "猪肝": ("肉禽", "温", "甘、苦", "养肝明目补血", "高胆固醇少食"),
    "羊肉": ("肉禽", "温", "甘", "温中补虚", "湿热阴虚者不宜"),
    "鸡肉": ("肉禽", "温", "甘", "温中益气", "感冒发热少食"),
    "乌鸡": ("肉禽", "平", "甘", "滋阴补血", None),
    "鸭肉": ("肉禽", "凉", "甘", "滋阴养胃", "脾胃虚寒少食"),
    "鲫鱼": ("水产", "平", "甘", "健脾利湿", "痛风慎食"),
    "鲢鱼头": ("水产", "温", "甘", "温中补虚", "过敏者禁用"),
    "莲藕": ("蔬菜", "寒(熟平)", "甘", "健脾开胃、益血生肌", "生食性寒"),
    "冬瓜": ("蔬菜", "凉", "甘、淡", "清热利水", "脾胃虚寒少食"),
    "白萝卜": ("蔬菜", "凉", "辛、甘", "下气消食", "脾胃虚寒少食"),
    "菠菜": ("蔬菜", "凉", "甘", "滋阴润燥、养血", "草酸高建议焯水"),
    "南瓜": ("蔬菜", "温", "甘", "补中益气", None),
    "绿豆": ("谷物", "寒", "甘", "清热解毒消暑", "脾胃虚寒少食"),
    "红豆": ("谷物", "平", "甘、酸", "健脾利水", None),
    "眉豆": ("谷物", "平", "甘", "健脾化湿", None),
    "花生": ("其他", "平", "甘", "健脾养胃", "过敏者禁用"),
    "核桃": ("其他", "温", "甘", "补肾健脑", "便溏少食"),
    "板栗": ("其他", "温", "甘", "补肾强筋", "腹胀少食"),
    "银耳": ("其他", "平", "甘、淡", "滋阴润肺养颜", None),
    "椰子": ("水果", "温", "甘", "补虚生津", None),
    "木瓜": ("水果", "温", "酸", "和胃化湿", None),
    "海棠果": ("水果", "平", "甘、微酸", "生津止渴", None),
    "柚子": ("水果", "寒", "甘、酸", "理气化痰", "脾胃虚寒少食"),
    "玫瑰花": ("调味", "温", "甘、微苦", "疏肝理气（非目录内花材）", "孕妇慎用"),
    "蜜枣": ("调味", "温", "甘", "补中调味", "含糖高"),
    "玉米须": ("其他", "平", "甘", "利水消肿（民间代茶食材）", None),
    "绿茶": ("茶叶", "凉", "苦、甘", "清热提神", "失眠者午后少饮"),
    "红茶": ("茶叶", "温", "甘", "温中提神", None),
}
foods_seen = {}
for r in RECIPES:
    for m in r["materials"]:
        if m["kind"] in ("普通食物", "茶叶"):
            foods_seen.setdefault(m["name"], m.get("note", ""))
for name, note in foods_seen.items():
    meta = FOOD_META.get(name)
    dst.execute("INSERT OR IGNORE INTO food(name,category,nature,flavor,functions,contraindication,note) VALUES (?,?,?,?,?,?,?)",
                (name, *(meta or (None, None, None, None, None)), "；".join(x for x in [note, "性味功效为编目暂录，待《中华本草》核对"] if x) or None))
print(f"普通食材: {len(foods_seen)} 种")

# ---------- 3. 方子表 ----------
dst.executescript("""
CREATE TABLE recipe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,             -- 茶饮/药膳
    oneliner TEXT, description TEXT, method TEXT, duration TEXT,
    scenes TEXT,                    -- JSON array
    constitutions_suitable TEXT,    -- JSON array
    constitutions_unsuitable TEXT,  -- JSON array
    population TEXT, contraindication TEXT,
    source TEXT, reference_url TEXT, status TEXT DEFAULT '待核对',
    analysis_ready INTEGER DEFAULT 0
);
CREATE INDEX idx_recipe_type ON recipe(type);
CREATE INDEX idx_recipe_status ON recipe(status);
CREATE TABLE rel_recipe_material (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER REFERENCES recipe(id),
    material_type TEXT NOT NULL,    -- herb/food
    herb_id TEXT REFERENCES herb(id),
    food_id INTEGER REFERENCES food(id),
    name TEXT NOT NULL, grams REAL, optional INTEGER DEFAULT 0, note TEXT
);
CREATE INDEX idx_rrm_recipe ON rel_recipe_material(recipe_id);
""")

def find_herb_id(name):
    row = dst.execute("SELECT id FROM herb WHERE name=?", (name,)).fetchone()
    return row[0] if row else None

def find_food_id(name):
    row = dst.execute("SELECT id FROM food WHERE name=?", (name,)).fetchone()
    return row[0] if row else None

# 卫健委目录内（含异名）的配料名：即使成分库无条目也标 herb/药食同源，
# 避免 决明子/莲子 这类目录品种被错标为普通食材
catalog_names = set(batch_by_alias.keys())

for r in RECIPES:
    ready = any(m.get("analysis_ready") for m in r["materials"])
    cur = dst.execute(
        "INSERT INTO recipe(name,type,oneliner,description,method,duration,scenes,"
        "constitutions_suitable,constitutions_unsuitable,population,contraindication,"
        "source,reference_url,status,analysis_ready) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (r["name"], r["type"], r.get("oneliner"), r.get("description"), r["method"], r.get("duration"),
         json.dumps(r.get("scenes", []), ensure_ascii=False),
         json.dumps(r.get("constitutions_suitable", []), ensure_ascii=False),
         json.dumps(r.get("constitutions_unsuitable", []), ensure_ascii=False),
         r.get("population"), r["contraindication"], r["source"], r.get("reference_url") or None,
         r.get("status", "待核对"), 1 if ready else 0))
    rid = cur.lastrowid
    for m in r["materials"]:
        if m.get("analysis_ready") or (m["kind"] == "药食同源" and find_herb_id(m["name"])):
            hid = find_herb_id(m["name"])
            dst.execute("INSERT INTO rel_recipe_material(recipe_id,material_type,herb_id,name,grams,optional,note) VALUES (?,?,?,?,?,?,?)",
                        (rid, "herb", hid, m["name"], m.get("grams"), 1 if m.get("optional") else 0, m.get("note")))
        elif m["name"] in catalog_names:
            # 目录内药材但成分库暂无条目：herb_id 置空、仍按药食同源标注
            dst.execute("INSERT INTO rel_recipe_material(recipe_id,material_type,herb_id,name,grams,optional,note) VALUES (?,?,?,?,?,?,?)",
                        (rid, "herb", None, m["name"], m.get("grams"), 1 if m.get("optional") else 0, m.get("note")))
        else:
            fid = find_food_id(m["name"])
            dst.execute("INSERT INTO rel_recipe_material(recipe_id,material_type,food_id,name,grams,optional,note) VALUES (?,?,?,?,?,?,?)",
                        (rid, "food", fid, m["name"], m.get("grams"), 1 if m.get("optional") else 0,
                         (m.get("note") or "") + ("；非目录内食材" if m["kind"] == "药食同源" and m["name"] not in batch_by_alias and fid is None and find_herb_id(m["name"]) is None else "")))

# ---------- 4. 体质表 ----------
dst.executescript("""
CREATE TABLE constitution (
    code TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL,
    typical_signs TEXT, principle TEXT,
    foods_suitable TEXT, foods_avoid TEXT, tea_ideas TEXT, lifestyle TEXT,
    reference_url TEXT, status TEXT DEFAULT '待核对'
);
CREATE TABLE constitution_food_ref (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    constitution_code TEXT REFERENCES constitution(code),
    direction TEXT NOT NULL,        -- suitable/avoid
    item TEXT NOT NULL,
    is_food_homology INTEGER DEFAULT 0
);
""")
for c in CONSTITUTION["constitutions"]:
    dst.execute(
        "INSERT INTO constitution(code,name,typical_signs,principle,foods_suitable,foods_avoid,tea_ideas,lifestyle,reference_url) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (c["code"], c["name"], json.dumps(c.get("typical_signs", []), ensure_ascii=False), c.get("principle"),
         json.dumps(c.get("foods_suitable", []), ensure_ascii=False), json.dumps(c.get("foods_avoid", []), ensure_ascii=False),
         json.dumps(c.get("tea_ideas", []), ensure_ascii=False), json.dumps(c.get("lifestyle", []), ensure_ascii=False),
         c.get("reference_url")))
    for item in c.get("foods_suitable", []):
        base = item.split("(")[0]
        dst.execute("INSERT INTO constitution_food_ref(constitution_code,direction,item,is_food_homology) VALUES (?,?,?,?)",
                    (c["code"], "suitable", base, 1 if "药食同源" in item else 0))
    for item in c.get("foods_avoid", []):
        base = item.split("(")[0]
        dst.execute("INSERT INTO constitution_food_ref(constitution_code,direction,item,is_food_homology) VALUES (?,?,?,?)",
                    (c["code"], "avoid", base, 1 if "药食同源" in item else 0))

# 量表判定规则存到 meta 表
dst.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
sr = CONSTITUTION.get("scoring_rule", {})
dst.executemany("INSERT OR REPLACE INTO meta(key,value) VALUES (?,?)", [
    ("ccmq_scoring", json.dumps(sr, ensure_ascii=False)),
    ("questionnaire", json.dumps(CONSTITUTION.get("questionnaire", {}), ensure_ascii=False)),
    ("questionnaire_note", json.dumps(CONSTITUTION.get("questionnaire_note", ""), ensure_ascii=False)),
    ("constitution_sources", json.dumps(CONSTITUTION.get("sources", []), ensure_ascii=False)),
    ("version", "shiyang v0.1"),
])

dst.commit()

# ---------- 5. 汇总 ----------
summary = {
    "herb": dst.execute("SELECT COUNT(*) FROM herb").fetchone()[0],
    "compound": dst.execute("SELECT COUNT(*) FROM compound").fetchone()[0],
    "target": dst.execute("SELECT COUNT(*) FROM target").fetchone()[0],
    "rel_compound_target": dst.execute("SELECT COUNT(*) FROM rel_compound_target").fetchone()[0],
    "food": dst.execute("SELECT COUNT(*) FROM food").fetchone()[0],
    "recipe": dst.execute("SELECT COUNT(*) FROM recipe").fetchone()[0],
    "recipe_tea": dst.execute("SELECT COUNT(*) FROM recipe WHERE type='茶饮'").fetchone()[0],
    "recipe_diet": dst.execute("SELECT COUNT(*) FROM recipe WHERE type='药膳'").fetchone()[0],
    "recipe_analysis_ready": dst.execute("SELECT COUNT(*) FROM recipe WHERE analysis_ready=1").fetchone()[0],
    "constitution": dst.execute("SELECT COUNT(*) FROM constitution").fetchone()[0],
}
dst.close(); src.close()
print("\n=== shiyang.db 构建完成 ===")
for k, v in summary.items():
    print(f"  {k}: {v}")
print(f"输出: {OUT}")
