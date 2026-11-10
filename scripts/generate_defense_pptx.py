# -*- coding: utf-8 -*-
"""
生成《食养有据》挑战杯答辩 PPT (.pptx) —— 极简大字·防挑刺版（Minimalist Defense Safe Edition）
核心策略：
1. 字少、字大、留白多：每张卡片只放 2~3 条短句（13.5pt~15pt），一眼看清核心数字与结论；
2. 零靶子设计：不把未标定的权重公式、测试集填补瑕疵、复杂子分类比例等容易引来评委追问的细枝末节印在屏幕上；
3. 细节留给备询：PPT 屏幕展示“最硬的指标 + 最直观的图”，把深度解释放进演讲者备注与 Q&A 锦囊。
"""
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DIAG_DIR = ROOT / "docs" / "diagrams"
SHOT_DIR = ROOT / "docs" / "screenshots"
OUT_PATH = ROOT / "docs" / "食养有据_挑战杯答辩PPT_侧重算法.pptx"

# 调色盘
C_BG = RGBColor(250, 248, 245)          # #FAF8F5 暖白底色
C_WHITE = RGBColor(255, 255, 255)       # #FFFFFF 纯白卡片
C_BORDER = RGBColor(203, 213, 225)      # #CBD5E1 边框

C_INK = RGBColor(15, 23, 42)            # #0F172A 深黑主标题
C_BODY = RGBColor(51, 65, 85)           # #334155 正文深灰
C_MUTED = RGBColor(100, 116, 139)       # #64748B 辅助说明灰

C_GREEN = RGBColor(5, 150, 105)         # #059669 本草翡翠绿
C_GREEN_DARK = RGBColor(6, 95, 70)      # #065F46 深本草绿
C_GREEN_BG = RGBColor(236, 253, 245)    # #ECFDF5 浅绿背景
C_GREEN_BD = RGBColor(110, 231, 183)    # #6EE7B7 浅绿边框

C_BLUE = RGBColor(29, 78, 216)          # #1D4ED8 算力天青蓝
C_BLUE_BG = RGBColor(239, 246, 255)     # #EFF6FF 浅蓝背景
C_BLUE_BD = RGBColor(147, 197, 253)     # #93C5FD 浅蓝边框

C_AMBER = RGBColor(180, 83, 9)          # #B45309 严谨琥珀金
C_AMBER_BG = RGBColor(255, 251, 235)    # #FFFBEB 浅琥珀背景
C_AMBER_BD = RGBColor(252, 211, 77)     # #FCD34D 浅琥珀边框

C_RED = RGBColor(220, 38, 38)           # #DC2626 预警珊瑚红
C_RED_BG = RGBColor(254, 242, 242)      # #FEF2F2 浅红背景
C_RED_BD = RGBColor(252, 165, 165)      # #FCA5A5 浅红边框

C_PURPLE = RGBColor(109, 40, 217)       # #6D28D9 交叉验证紫
C_PURPLE_BG = RGBColor(245, 243, 255)   # #F5F3FF 浅紫背景

DISCLAIMER_TEXT = "本平台内容为健康参考信息，不构成医疗建议，不用于诊断或治疗。"


def add_bg(slide, page_num: int = 0, total_pages: int = 16):
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = C_BG
    bg.line.fill.background()

    top_bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(0.08))
    top_bar.fill.solid()
    top_bar.fill.fore_color.rgb = C_GREEN
    top_bar.line.fill.background()

    if page_num > 0:
        tb = slide.shapes.add_textbox(Inches(0.6), Inches(7.12), Inches(12.133), Inches(0.3))
        tf = tb.text_frame
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.text = f"食养有据 (Shiyang) · 挑战杯答辩汇报    |    {DISCLAIMER_TEXT}    |    {page_num:02d} / {total_pages:02d}"
        p.font.size = Pt(9.5)
        p.font.color.rgb = C_MUTED


def add_header(slide, tag: str, title: str, subtitle: str = "", tag_color=C_GREEN, tag_bg=C_GREEN_BG):
    pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(0.28), Inches(2.5), Inches(0.32))
    pill.fill.solid()
    pill.fill.fore_color.rgb = tag_bg
    pill.line.color.rgb = tag_color
    pill.line.width = Pt(1)
    p0 = pill.text_frame.paragraphs[0]
    p0.text = tag.upper()
    p0.alignment = PP_ALIGN.CENTER
    p0.font.size = Pt(9.5)
    p0.font.bold = True
    p0.font.color.rgb = tag_color

    tb = slide.shapes.add_textbox(Inches(0.6), Inches(0.64), Inches(12.133), Inches(0.82))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

    p1 = tf.paragraphs[0]
    p1.text = title
    p1.font.size = Pt(22)
    p1.font.bold = True
    p1.font.color.rgb = C_INK

    if subtitle:
        p2 = tf.add_paragraph()
        p2.text = subtitle
        p2.font.size = Pt(12)
        p2.font.color.rgb = C_MUTED
        p2.space_before = Pt(3)


def add_card(slide, left, top, width, height, title="", title_color=C_GREEN_DARK, bg_color=C_WHITE, border_color=C_BORDER):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = bg_color
    shape.line.color.rgb = border_color
    shape.line.width = Pt(1.2)
    shape.adjustments[0] = 0.03

    if title:
        tb = slide.shapes.add_textbox(left + Inches(0.22), top + Inches(0.16), width - Inches(0.44), Inches(0.4))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.text = title
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = title_color
    return shape


def add_bullets(slide, left, top, width, height, items, font_size=13.5, space_after=10):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

    for idx, item in enumerate(items):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.space_after = Pt(space_after)
        if isinstance(item, tuple):
            bold_part, rest_part = item[0], item[1]
            col = item[2] if len(item) > 2 else C_INK
            r1 = p.add_run()
            r1.text = bold_part
            r1.font.bold = True
            r1.font.size = Pt(font_size)
            r1.font.color.rgb = col
            r2 = p.add_run()
            r2.text = rest_part
            r2.font.bold = False
            r2.font.size = Pt(font_size)
            r2.font.color.rgb = C_BODY
        else:
            p.text = item
            p.font.size = Pt(font_size)
            p.font.color.rgb = C_BODY
    return tb


def add_picture_fit(slide, img_path: Path, left, top, max_w, max_h, caption: str = ""):
    if not img_path.exists():
        return None
    with Image.open(img_path) as im:
        w_px, h_px = im.size
    ratio = w_px / float(h_px)

    avail_h = max_h - (Inches(0.28) if caption else 0)
    target_w = max_w
    target_h = int(target_w / ratio)
    if target_h > avail_h:
        target_h = avail_h
        target_w = int(target_h * ratio)

    offset_x = left + int((max_w - target_w) / 2)
    offset_y = top + int((avail_h - target_h) / 2)
    pic = slide.shapes.add_picture(str(img_path), offset_x, offset_y, width=target_w, height=target_h)

    if caption:
        tb = slide.shapes.add_textbox(left, top + avail_h + Inches(0.02), max_w, Inches(0.24))
        tf = tb.text_frame
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.text = caption
        p.alignment = PP_ALIGN.CENTER
        p.font.size = Pt(10)
        p.font.bold = True
        p.font.color.rgb = C_MUTED
    return pic


def add_phone_mockup(slide, img_path: Path, left, top, width, height, caption: str = "", badge_color=C_GREEN):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    card.fill.solid()
    card.fill.fore_color.rgb = C_WHITE
    card.line.color.rgb = badge_color
    card.line.width = Pt(1.5)
    card.adjustments[0] = 0.04

    if caption:
        tb = slide.shapes.add_textbox(left + Inches(0.08), top + Inches(0.06), width - Inches(0.16), Inches(0.28))
        tf = tb.text_frame
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.text = caption
        p.alignment = PP_ALIGN.CENTER
        p.font.size = Pt(10.5)
        p.font.bold = True
        p.font.color.rgb = badge_color
        img_top = top + Inches(0.34)
        img_h = height - Inches(0.42)
    else:
        img_top = top + Inches(0.08)
        img_h = height - Inches(0.16)

    add_picture_fit(slide, img_path, left + Inches(0.08), img_top, width - Inches(0.16), img_h)


def add_kpi_box(slide, left, top, width, height, num_str: str, label_str: str, sub_str: str, accent=C_GREEN, bg=C_WHITE):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    card.fill.solid()
    card.fill.fore_color.rgb = bg
    card.line.color.rgb = accent
    card.line.width = Pt(1.5)
    card.adjustments[0] = 0.06

    tb = slide.shapes.add_textbox(left + Inches(0.16), top + Inches(0.1), width - Inches(0.32), height - Inches(0.2))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

    p0 = tf.paragraphs[0]
    p0.text = num_str
    p0.font.size = Pt(22)
    p0.font.bold = True
    p0.font.color.rgb = accent

    p1 = tf.add_paragraph()
    p1.text = label_str
    p1.font.size = Pt(12)
    p1.font.bold = True
    p1.font.color.rgb = C_INK
    p1.space_before = Pt(3)

    p2 = tf.add_paragraph()
    p2.text = sub_str
    p2.font.size = Pt(10)
    p2.font.color.rgb = C_MUTED
    p2.space_before = Pt(2)


def add_notes(slide, notes_text: str):
    slide.notes_slide.notes_text_frame.text = notes_text.strip()


def build_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # =========================================================================
    # SLIDE 01: 封面（少字大气）
    # =========================================================================
    s1 = prs.slides.add_slide(blank)
    add_bg(s1, page_num=1)

    pill = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(0.5), Inches(3.5), Inches(0.38))
    pill.fill.solid()
    pill.fill.fore_color.rgb = C_GREEN_BG
    pill.line.color.rgb = C_GREEN
    p = pill.text_frame.paragraphs[0]
    p.text = "全国大学生「挑战杯」竞赛答辩汇报"
    p.alignment = PP_ALIGN.CENTER
    p.font.size = Pt(11.5)
    p.font.bold = True
    p.font.color.rgb = C_GREEN_DARK

    tb1 = s1.shapes.add_textbox(Inches(0.6), Inches(1.08), Inches(6.5), Inches(2.1))
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    tf1.margin_left = tf1.margin_top = tf1.margin_right = tf1.margin_bottom = 0
    p = tf1.paragraphs[0]
    p.text = "食养有据 (Shiyang)"
    p.font.size = Pt(38)
    p.font.bold = True
    p.font.color.rgb = C_INK
    p.space_after = Pt(8)

    p2 = tf1.add_paragraph()
    p2.text = "基于 PU-Learning 入血预测与计算生物学机制的\n药食同源精准分析推荐平台"
    p2.font.size = Pt(17)
    p2.font.bold = True
    p2.font.color.rgb = C_GREEN_DARK
    p2.space_after = Pt(8)

    p3 = tf1.add_paragraph()
    p3.text = "为每一杯食养茶饮开具科学可信的「成分说明书」"
    p3.font.size = Pt(13)
    p3.font.color.rgb = C_MUTED

    kw, kh = Inches(3.15), Inches(1.22)
    add_kpi_box(s1, Inches(0.6), Inches(3.35), kw, kh, "105 味 / 73 方", "国家卫健委药食同源名录", "经典茶饮与药膳汤羹全覆盖", C_GREEN, C_WHITE)
    add_kpi_box(s1, Inches(3.95), Inches(3.35), kw, kh, "4,562 分子", "三档入血倾向预测", "ROC-AUC 0.903 ± 0.008", C_BLUE, C_WHITE)
    add_kpi_box(s1, Inches(0.6), Inches(4.75), kw, kh, "10,154 靶点", "62,617 条成分-靶点互作", "ChEMBL 465 条体外实测背书", C_AMBER, C_WHITE)
    add_kpi_box(s1, Inches(3.95), Inches(4.75), kw, kh, "57 路径 / 61 端点", "全栈高可用与适老模式", "Web 端 + 原生安卓 APK", C_PURPLE, C_WHITE)

    add_card(s1, Inches(0.6), Inches(6.15), Inches(6.5), Inches(0.8), "", bg_color=C_GREEN_BG, border_color=C_GREEN_BD)
    add_bullets(s1, Inches(0.8), Inches(6.28), Inches(6.1), Inches(0.55), [
        ("● 数据底座：", "南京中医药大学赵玉男教授团队 ccTCM 2.0 原始库  |  ", C_GREEN_DARK),
        ("● 汇报团队：", "食养有据研发组", C_INK),
    ], font_size=11.5, space_after=2)

    add_card(s1, Inches(7.35), Inches(0.5), Inches(5.4), Inches(6.45), "本草活性分子 → 体内入血预测 → 靶点网络 → 智能推荐", C_GREEN_DARK)
    add_picture_fit(s1, DIAG_DIR / "hero_cover_light.jpg", Inches(7.5), Inches(1.0), Inches(5.1), Inches(2.95))
    add_phone_mockup(s1, SHOT_DIR / "01-home.png", Inches(7.55), Inches(4.05), Inches(2.4), Inches(2.75), "实机首页", C_GREEN)
    add_phone_mockup(s1, SHOT_DIR / "audit_2026-11-07" / "t1_甘草_detail.png", Inches(10.15), Inches(4.05), Inches(2.4), Inches(2.75), "105 味药材库", C_BLUE)

    add_notes(s1, """【Slide 01 演讲稿（30 秒）】
各位评委老师好！我是《食养有据》项目汇报人。
大家平时喝养生茶、煲药膳汤时，最常问三个问题：“里面有什么有效成分？喝下去能不能吸收进血液？到底适不适合我的体质？”
我们的项目基于南京中医药大学赵玉男教授团队的 ccTCM 2.0 数据底座，构建了 PU-Learning 入血成分预测模型，覆盖国家卫健委 105 味药食同源目录、4,562 个分子预测和 1 万多个蛋白靶点，为每一杯食养茶饮开具科学可信的“成分说明书”。""")

    # =========================================================================
    # SLIDE 02: 立项背景与核心痛点（精简三卡片 + 实机图）
    # =========================================================================
    s2 = prs.slides.add_slide(blank)
    add_bg(s2, page_num=2)
    add_header(s2, "01 · Background", "立项背景与核心痛点：破除传统食疗「成分黑盒」",
               "从经验养生走向计算有据，解决“不入血就难起效”与“无真实负样本”两大瓶颈")

    col_w = Inches(2.95)
    top_y = Inches(1.58)
    ch = Inches(5.3)

    add_card(s2, Inches(0.6), top_y, col_w, ch, "1. 传统食疗痛点", C_AMBER, C_AMBER_BG, C_AMBER_BD)
    add_bullets(s2, Inches(0.82), top_y + Inches(0.65), col_w - Inches(0.44), ch - Inches(0.8), [
        ("● 成分如黑盒：\n", "只讲古籍概念，缺乏现代分子与靶点依据。", C_AMBER),
        ("● 剂量无参考：\n", "不清楚喝一杯茶能摄入多少毫克有效成分。", C_AMBER),
        ("● 禁忌缺拦截：\n", "体质相冲与特殊人群缺乏自动安全过滤。", C_AMBER),
    ], font_size=13.5, space_after=14)

    add_card(s2, Inches(3.72), top_y, col_w, ch, "2. 传统网药瓶颈", C_RED, C_RED_BG, C_RED_BD)
    add_bullets(s2, Inches(3.94), top_y + Inches(0.65), col_w - Inches(0.44), ch - Inches(0.8), [
        ("● 忽视入血壁垒：\n", "把药材全部成分等权拿去算靶点，假阳性高。", C_RED),
        ("● 文献无真负例：\n", "只报道“血中检出了什么”(13%)，不报“没检出什么”。", C_RED),
        ("● 常规分类失效：\n", "缺负样本导致传统二分类模型偏差大。", C_RED),
    ], font_size=13.5, space_after=14)

    add_card(s2, Inches(6.84), top_y, col_w, ch, "3. 本项目破局方案", C_GREEN_DARK, C_GREEN_BG, C_GREEN_BD)
    add_bullets(s2, Inches(7.06), top_y + Inches(0.65), col_w - Inches(0.44), ch - Inches(0.8), [
        ("● PU-Learning 建模：\n", "从正例与未标注样本中学习入血倾向 (AUC 0.903)。", C_GREEN_DARK),
        ("● 可信度四件套：\n", "适用域预警 + ChEMBL 实测 + 跨算法互验 + 暴露量区间。", C_GREEN_DARK),
        ("● 普惠产品落地：\n", "端侧识方纠错、茶罐反向配伍、长辈大字模式。", C_GREEN_DARK),
    ], font_size=13.5, space_after=14)

    add_phone_mockup(s2, SHOT_DIR / "audit_2026-11-07" / "t2_recipe1_sentence_card.png",
                     Inches(10.0), top_y, Inches(2.73), ch, "实机：方子「成分一句话」", C_GREEN)

    add_notes(s2, """【Slide 02 演讲稿（40 秒）】
为什么我们要做这个课题？
一方面，传统食疗产品往往只讲概念，缺乏分子层面的证据；
另一方面，传统网络药理学把药材里所有成分等权拿去算靶点，忽略了“成分不入血就很难到达全身靶点”的药代常识。
但要用 AI 预测中药成分入血，最大的难题是“没有负样本”——因为文献只发表在血里检出了什么，从来不发表没检出什么。
为此，我们引入了正样本-未标注学习（PU-Learning），并配套构建了可信度四件套与大众化食养平台。""")

    # =========================================================================
    # SLIDE 03: 总体系统架构图（全幅极简大图）
    # =========================================================================
    s3 = prs.slides.add_slide(blank)
    add_bg(s3, page_num=3)
    add_header(s3, "02 · Architecture", "总体系统技术架构与五层算法全景",
               "数据底座 → 分子指纹表征 → 核心算法矩阵 → 协同决策 → 多端适老交付", C_BLUE, C_BLUE_BG)

    add_picture_fit(s3, DIAG_DIR / "diagram_system_architecture.png",
                    Inches(0.55), Inches(1.5), Inches(12.23), Inches(5.5))

    add_notes(s3, """【Slide 03 演讲稿（40 秒）】
这是平台的五层总体架构：
底层整合卫健委 105 味药食同源目录、ccTCM 2.0 原始库与 ChEMBL 实测数据；
第二层通过 RDKit 提取 1024 位 Morgan 分子指纹与理化参数；
第三层是核心算法层，包含 PU-Learning 入血预测、三档口径分层、留一法适用域、UMAP 化学空间映射，以及本地 OCR 与本草形近字纠错；
上两层支撑茶罐反向配伍、对比实验室、体质安全推荐以及长辈大字版，通过 57 个后端路径提供毫秒级服务。""")

    # =========================================================================
    # SLIDE 04: 算法核心一：PU-Learning 建模与机理（全幅极简大图）
    # =========================================================================
    s4 = prs.slides.add_slide(blank)
    add_bg(s4, page_num=4)
    add_header(s4, "03 · Algorithm 01: PU-Learning", "算法核心一：PU-Learning 入血预测与「检出倾向」机理",
               "解决无真负例难题；科学阐明模型预测的是「血中检出倾向」而非「原形口服吸收率」", C_BLUE, C_BLUE_BG)

    add_picture_fit(s4, DIAG_DIR / "diagram_algorithm_pulearning.png",
                    Inches(0.55), Inches(1.5), Inches(12.23), Inches(5.5))

    add_notes(s4, """【Slide 04 演讲稿（50 秒）】
第一个核心算法是 PU-Learning 入血预测。
针对 282 个正样本与 1,887 个未标注样本，我们采用 30 轮 PU-Bagging 均衡重采样训练随机森林，软投票集成消解噪声，测试集 ROC-AUC 达到 0.903。
这里有一个非常关键的科学认知：我们的模型预测的是“血中移行检出倾向”，而不是原形分子的“口服吸收率”。
比如图左下角的人参皂苷 Re，分子量 947，直接透膜吸收率低，但经过肠道菌群水解后代谢物大量入血，实验检出率极高，因此模型给出 0.991 高分；而右下角的小分子石竹烯虽然易透膜，但肝脏首过代谢极快，血中很难测到原型峰，所以得分仅 0.046。模型准确反映了中药体内的真实代谢规律。""")

    # =========================================================================
    # SLIDE 05: 算法核心二：三档口径与消融实验
    # =========================================================================
    s5 = prs.slides.add_slide(blank)
    add_bg(s5, page_num=5)
    add_header(s5, "04 · Algorithm 02: Ablation Study", "算法核心二：模型评估与 4,562 分子三档口径消融治理",
               "通过消融实验拒绝盲目外推，实现 A/B/C 三档预测口径透明隔离", C_AMBER, C_AMBER_BG)

    mw, mh = Inches(2.9), Inches(1.0)
    add_kpi_box(s5, Inches(0.6), Inches(1.5), mw, mh, "0.903 ± 0.008", "测试集 ROC-AUC", "3 随机种子交叉验证", C_GREEN)
    add_kpi_box(s5, Inches(3.7), Inches(1.5), mw, mh, "0.573 ± 0.009", "测试集 PR-AUC", "最优 F1 = 0.585", C_BLUE)
    add_kpi_box(s5, Inches(6.8), Inches(1.5), mw, mh, "prob ≥ 0.7", "高置信展示截断线", "精确率提升至 54.9%", C_AMBER)
    add_kpi_box(s5, Inches(9.9), Inches(1.5), mw, mh, "0.290 → 0.135", "消融外推偏差减半", "切换结构兜底模型", C_RED)

    add_picture_fit(s5, DIAG_DIR / "chart_ablation_caliber.png",
                    Inches(0.55), Inches(2.6), Inches(12.23), Inches(4.4))

    add_notes(s5, """【Slide 05 演讲稿（50 秒）】
主模型取得了 0.903 的 ROC-AUC，并在展示端采用 0.7 的高置信截断线。
当我们将药材扩充到 105 味、分子扩充到 4,562 个时，有 3,602 个训练集外的新分子缺少主模型所需的实验室 ADME 参数。
为此我们做了消融实验（见右表）：如果强行补齐特征跑主模型，平均偏差高达 0.290，分类翻转率达 44.4%；而改用仅依赖化学结构的兜底模型，平均偏差降到 0.135，一致率达 79%。
因此我们建立了 A、B、C 三档口径分层，并在界面上对 C 类分子诚实标注“外推参考”。""")

    # =========================================================================
    # SLIDE 06: 跨算法族交叉验证
    # =========================================================================
    s6 = prs.slides.add_slide(blank)
    add_bg(s6, page_num=6)
    add_header(s6, "05 · Algorithm 03: Cross-Validation", "算法鲁棒性：跨算法族独立验证与一致性分析",
               "三种不同范式算法独立重训，判别能力高度吻合，分类一致率达 73.9%", C_PURPLE, C_PURPLE_BG)

    add_picture_fit(s6, DIAG_DIR / "chart_cross_validation.png",
                    Inches(0.55), Inches(1.52), Inches(9.15), Inches(5.45))

    add_phone_mockup(s6, SHOT_DIR / "04-compound.png",
                     Inches(9.88), Inches(1.52), Inches(2.85), Inches(5.45),
                     "实机：落新妇苷双模型对比", C_AMBER)

    add_notes(s6, """【Slide 06 演讲稿（40 秒）】
为了验证结论不依赖单一算法，我们用提升树 XGBoost、神经网络 MLP 和逻辑回归进行了独立重训。
其中独立 XGBoost 的 AUC 达到 0.896，与主模型 0.903 非常接近；两套模型在核心成分上的分类一致率达到 73.9%。
少量存在分歧的成分（如右图的落新妇苷）主要集中在大分子和糖苷类，源于 PU 学习对未标注苷类代谢物更宽容，我们在页面上直接向用户透明展示双模型对比条。""")

    # =========================================================================
    # SLIDE 07: 留一法适用域与可信度四件套
    # =========================================================================
    s7 = prs.slides.add_slide(blank)
    add_bg(s7, page_num=7)
    add_header(s7, "06 · Algorithm 04: Applicability Domain", "算法边界：留一法 (LOO) 适用域量化与「可信度四件套」",
               "量化每个分子与训练集的最大结构相似度，超出模型能力范围主动亮红牌预警", C_GREEN_DARK, C_GREEN_BG)

    add_picture_fit(s7, DIAG_DIR / "diagram_credibility_quartet.png",
                    Inches(0.55), Inches(1.52), Inches(9.15), Inches(5.45))

    add_phone_mockup(s7, SHOT_DIR / "12-compound-ad-out.png",
                     Inches(9.88), Inches(1.52), Inches(2.85), Inches(5.45),
                     "实机：白皮杉醇「应用域外」", C_RED)

    add_notes(s7, """【Slide 07 演讲稿（40 秒）】
AI 模型最怕在陌生结构上盲目外推。我们采用留一法计算每个分子与训练集的最大 Morgan 指纹相似度，标定出应用域内、边缘和域外三条分界线。
如右图实机界面所示，当遇到与训练集结构差异较大的“白皮杉醇”（相似度仅 0.246），系统直接亮起红色“应用域外”徽章，主动提示预测可靠性有限。
适用域预警、ChEMBL 实测活性、跨算法互验与三档暴露量，共同组成了平台的“科学可信度四件套”。""")

    # =========================================================================
    # SLIDE 08: UMAP 化学空间流形
    # =========================================================================
    s8 = prs.slides.add_slide(blank)
    add_bg(s8, page_num=8)
    add_header(s8, "07 · Algorithm 05: Chemical Space", "拓扑表征：全库 4,558 分子 UMAP 化学空间地图",
               "将 1024 维分子指纹降维至二维平面，直观呈现骨架聚类与入血概率分布", C_BLUE, C_BLUE_BG)

    add_picture_fit(s8, DIAG_DIR / "chart_umap_manifold.png",
                    Inches(0.55), Inches(1.52), Inches(9.15), Inches(5.45))

    add_phone_mockup(s8, SHOT_DIR / "05-chem-map.png",
                     Inches(9.88), Inches(1.52), Inches(2.85), Inches(5.45),
                     "实机：/chem-map 化学空间", C_BLUE)

    add_notes(s8, """【Slide 08 演讲稿（30 秒）】
我们将全库 4,558 个分子的 1024 维指纹通过 UMAP 投影为二维化学空间地图。
从左图真实散点和右图手机界面可以看到，黄酮、皂苷等不同骨架自然聚成岛礁，高入血分子呈现明显的空间富集，用户可随时切换入血概率、应用域和模型一致性三种视角。""")

    # =========================================================================
    # SLIDE 09: ChEMBL 实验活性与三维评价指数
    # =========================================================================
    s9 = prs.slides.add_slide(blank)
    add_bg(s9, page_num=9)
    add_header(s9, "08 · Mechanism & 3D Index", "机制解析：ChEMBL 实验实测背书与「食养科学三维指数」",
               "接入 465 条体外实测活性数据；建立覆盖全库 73 方的入血潜力·多靶协同·证据强度三维评分", C_GREEN_DARK, C_GREEN_BG)

    add_picture_fit(s9, DIAG_DIR / "chart_target_3d_index.png",
                    Inches(0.55), Inches(1.52), Inches(9.15), Inches(5.45))

    add_phone_mockup(s9, SHOT_DIR / "13-compound-chembl.png",
                     Inches(9.88), Inches(1.52), Inches(2.85), Inches(5.45),
                     "实机：黄芩素 ChEMBL 实测", C_GREEN)

    add_notes(s9, """【Slide 09 演讲稿（45 秒）】
为了让证据链不仅有模型预测、更有实验支撑，我们对接了欧洲生物信息研究所 ChEMBL 数据库，入库 465 条人类蛋白靶点体外实测 Ki/IC50 记录，其中 127 条达到微摩尔级 L1 强证据（右图为黄芩素的实测靶点列表）。
在此基础上，我们面向全平台 73 首方剂构建了「食养科学三维评价指数」：从入血潜力、多靶协同、证据强度三个维度给出客观评分。""")

    # =========================================================================
    # SLIDE 10: 剂量模拟与科普下放（精简大字版）
    # =========================================================================
    s10 = prs.slides.add_slide(blank)
    add_bg(s10, page_num=10)
    add_header(s10, "09 · Dose & Popularization", "剂量估算与科研下放：三档暴露量区间与大众科普卡",
               "给诚实区间、不给假单点；将专业药化参数转化为百姓看得懂的一句话结论", C_AMBER, C_AMBER_BG)

    add_card(s10, Inches(0.6), Inches(1.55), Inches(6.5), Inches(2.6),
             "1. 暴露量三档情景估算（给区间，不给假单点）", C_AMBER, C_WHITE, C_AMBER_BD)
    add_bullets(s10, Inches(0.85), Inches(2.15), Inches(6.0), Inches(1.85), [
        ("● 估算模型：", "药材克重 × 文献含量区间 × 煎煮转移率", C_AMBER),
        ("● 三档情景：", "设 保守 (0.3) / 基准 (0.5) / 乐观 (0.7) 三档，输出毫克级摄入区间 [min, max] mg。", C_INK),
    ], font_size=14, space_after=12)

    add_card(s10, Inches(0.6), Inches(4.35), Inches(6.5), Inches(2.6),
             "2. 科研功能大众化下放（外行看门道，内行看证据）", C_GREEN_DARK, C_WHITE, C_GREEN_BD)
    add_bullets(s10, Inches(0.85), Inches(4.95), Inches(6.0), Inches(1.85), [
        ("● 方子「成分一句话卡」：", "首屏直接汇总核心高入血成分数量与通俗作用。", C_GREEN_DARK),
        ("● Lipinski 规则通俗化：", "先给“小分子易穿肠入血”人话结论，专业参数支持一键展开。", C_BLUE),
    ], font_size=14, space_after=12)

    add_phone_mockup(s10, SHOT_DIR / "03-recipe-detail.png",
                     Inches(7.35), Inches(1.55), Inches(2.6), Inches(5.4), "实机：银菊利咽茶详情", C_GREEN)
    add_phone_mockup(s10, SHOT_DIR / "audit_2026-11-06" / "22_lipinski_expanded.png",
                     Inches(10.15), Inches(1.55), Inches(2.6), Inches(5.4), "实机：Lipinski 通俗解读", C_AMBER)

    add_notes(s10, """【Slide 10 演讲稿（35 秒）】
考虑到茶饮冲泡受火候、时间影响很大，我们在计算有效成分暴露量时，拒绝给出虚假的单点数字，而是按保守 0.3、基准 0.5、乐观 0.7 三档转移率呈现摄入区间。
同时，我们在前端推出了“成分一句话结论卡”和通俗化的 Lipinski 解读，让普通用户一眼看懂，专业人士点开也能查到完整参数。""")

    # =========================================================================
    # SLIDE 11: 端侧 OCR 与形近字纠错（精简大字版）
    # =========================================================================
    s11 = prs.slides.add_slide(blank)
    add_bg(s11, page_num=11)
    add_header(s11, "10 · Edge AI & Typo Repair", "端侧突破：本地纯 CPU 识方与本草形近字拓扑纠错",
               "零 API 成本断网可用；攻克“OCR 认错一字导致后续成分靶点全空”的落地痛点", C_BLUE, C_BLUE_BG)

    add_card(s11, Inches(0.6), Inches(1.55), Inches(4.45), Inches(5.4),
             "1. 本地轻量 RapidOCR (ONNX)", C_BLUE, C_WHITE, C_BLUE_BD)
    add_bullets(s11, Inches(0.85), Inches(2.2), Inches(3.95), Inches(4.5), [
        ("● 纯 CPU 离线秒级推理：\n", "脱离云端大模型 API 依赖，零调用成本、断网可用。", C_BLUE),
        ("● 三档劣化图 100% 召回：\n",
         "• 清晰标准图：1.5s\n"
         "• 中度模糊图：3.6s\n"
         "• 极端倾斜暗光图：2.9s", C_GREEN_DARK),
        ("● 自动置信过滤：\n", "剔除低置信度背景杂字干扰。", C_INK),
    ], font_size=13.5, space_after=12)

    add_card(s11, Inches(5.22), Inches(1.55), Inches(4.45), Inches(5.4),
             "2. 本草形近字纠错算法", C_PURPLE, C_WHITE, C_BORDER)
    add_bullets(s11, Inches(5.47), Inches(2.2), Inches(3.95), Inches(4.5), [
        ("● 三级受限本草词表纠偏：\n",
         "① 形近字替换：金银化 → 金银花\n"
         "② 省字补全：枸札 → 枸杞子\n"
         "③ 受限距离：阵皮 → 陈皮", C_PURPLE),
        ("● 防误伤安全锁：\n", "多候选歧义拒猜，绝不把「桂圆」乱猜成「桂枝」。", C_AMBER),
        ("★ 实测准确率：\n", "错字纠错率 11/12，真药名误纠率 0/40！", C_GREEN_DARK),
    ], font_size=13.5, space_after=12)

    add_phone_mockup(s11, SHOT_DIR / "14-custom-recipe.png",
                     Inches(9.88), Inches(1.55), Inches(2.85), Inches(5.4), "实机：自定义鉴方识方", C_PURPLE)

    add_notes(s11, """【Slide 11 演讲稿（40 秒）】
用户拍照录入药方时，普通 OCR 经常把“金银花”认成“金银化”、“枸杞”认成“枸札”。错一个字，后续靶点查询就会全部落空。
我们采用本地纯 CPU 运行的 RapidOCR，配合自研的本草形近字三级纠错算法，在 800 余味本草词表约束下，实现了 11/12 的错字纠错率，且对真实药名的误伤率是 0/40，断网也能毫秒级完成纠偏。""")

    # =========================================================================
    # SLIDE 12: 我的茶罐与对比实验室（精简大字版）
    # =========================================================================
    s12 = prs.slides.add_slide(blank)
    add_bg(s12, page_num=12)
    add_header(s12, "11 · Core Applications", "核心应用：「我的茶罐」反向配伍与「对比实验室」",
               "从“按方抓药”变为“翻茶罐随手组方”，支持多方并排深度比对", C_GREEN_DARK, C_GREEN_BG)

    add_card(s12, Inches(0.6), Inches(1.55), Inches(6.5), Inches(2.6),
             "1. 【我的茶罐】食材子集图覆盖算法", C_GREEN_DARK, C_WHITE, C_GREEN_BD)
    add_bullets(s12, Inches(0.85), Inches(2.15), Inches(6.0), Inches(1.85), [
        ("● 五大分类货架 + 俗名检索：", "搜“桂圆”自动匹配“龙眼肉”，勾选家中现有食材即可反向组方。", C_GREEN_DARK),
        ("● 智能三级排序：", "按「直接能煮 → 差一味可凑 → 高入血活性成分数」自动推荐最优方。", C_INK),
    ], font_size=13.5, space_after=12)

    add_card(s12, Inches(0.6), Inches(4.35), Inches(6.5), Inches(2.6),
             "2. 【对比实验室】双槽位同屏 PK", C_AMBER, C_WHITE, C_AMBER_BD)
    add_bullets(s12, Inches(0.85), Inches(4.95), Inches(6.0), Inches(1.85), [
        ("● 两方并排深度对比：", "一键比对共有/独有配料、高入血成分重合度与生物靶点通路。", C_AMBER),
        ("● 自定义鉴方打通：", "民间自拟方也能实时测算成分与靶点证据。", C_BLUE),
    ], font_size=13.5, space_after=12)

    add_phone_mockup(s12, SHOT_DIR / "11-pantry.png",
                     Inches(7.35), Inches(1.55), Inches(2.6), Inches(5.4), "实机：已选5味→能煮2道", C_GREEN)
    add_phone_mockup(s12, SHOT_DIR / "08-compare.png",
                     Inches(10.15), Inches(1.55), Inches(2.6), Inches(5.4), "实机：两方同屏并排对比", C_AMBER)

    add_notes(s12, """【Slide 12 演讲稿（40 秒）】
在应用层，我们打造了“我的茶罐”和“对比实验室”（见右侧真机截图）。
针对年轻人手头有枸杞、菊花、麦冬却不知怎么搭的场景，在“我的茶罐”勾选 5 味食材，系统立刻算出“今晚直接能煮 2 道、差一味可凑 8 道”；
而在“对比实验室”中，可以把两个相似方子并排 PK，清晰对比配料差异与入血成分覆盖。""")

    # =========================================================================
    # SLIDE 13: 体质辨识与安全剪枝推荐（精简大字版）
    # =========================================================================
    s13 = prs.slides.add_slide(blank)
    add_bg(s13, page_num=13)
    add_header(s13, "12 · Safe Recommendation", "推荐引擎：国标 CCMQ 67 题体质测评与安全红线剪枝",
               "安全规则一票否决优先于推荐打分，结合 24 节气与家庭成员档案精准推荐", C_BLUE, C_BLUE_BG)

    add_picture_fit(s13, DIAG_DIR / "diagram_pantry_recommendation.png",
                    Inches(0.55), Inches(1.52), Inches(9.15), Inches(3.45))

    add_card(s13, Inches(0.6), Inches(5.12), Inches(9.05), Inches(1.83),
             "双重保障：先过安全红线门 (Safety Gate)，再做多维协同推荐", C_GREEN_DARK, C_WHITE, C_GREEN_BD)
    add_bullets(s13, Inches(0.85), Inches(5.62), Inches(8.6), Inches(1.2), [
        ("● 第一步（禁忌一票否决）：", "孕哺/儿童/慢病禁忌与相冲体质直接硬拦截，支持切换父母伴侣档案。", C_RED),
        ("● 第二步（多维协同排序）：", "综合主导体质匹配度、24 节气时令主题与方剂高入血成分丰度生成推荐。", C_INK),
    ], font_size=13, space_after=8)

    add_phone_mockup(s13, SHOT_DIR / "06-quiz.png",
                     Inches(9.88), Inches(1.52), Inches(2.85), Inches(5.45), "实机：CCMQ 67 题体质测评", C_BLUE)

    add_notes(s13, """【Slide 13 演讲稿（35 秒）】
在个性化推荐上，我们内置了中华中医药学会标准的 CCMQ 67 题体质量表。
推荐计算时坚持“安全第一”：先通过安全门把体质相冲和孕哺禁忌一票否决，再结合用户体质、24 节气时令和高入血成分丰度给出推荐理由。""")

    # =========================================================================
    # SLIDE 14: 全栈工程与长辈适老模式（精简大字版）
    # =========================================================================
    s14 = prs.slides.add_slide(blank)
    add_bg(s14, page_num=14)
    add_header(s14, "13 · Engineering & Accessibility", "全栈工程实现与全局「长辈大字版」适老无障碍模式",
               "双数据库动静隔离 · 106 项自动化单测全通过 · 科技向善消除银发数字鸿沟", C_GREEN_DARK, C_GREEN_BG)

    add_card(s14, Inches(0.6), Inches(1.55), Inches(6.5), Inches(2.6),
             "1. 高可用全栈架构与数据只读防篡改", C_BLUE, C_WHITE, C_BLUE_BD)
    add_bullets(s14, Inches(0.85), Inches(2.15), Inches(6.0), Inches(1.85), [
        ("● 双库动静隔离：", "科研知识库只读挂载 (mode=ro) 零篡改，用户库 WAL 并发读写。", C_BLUE),
        ("● 57 路径 / 106 单测：", "核心接口响应 < 15ms，支持 Web 端与原生 Android APK 交付。", C_INK),
    ], font_size=13.5, space_after=12)

    add_card(s14, Inches(0.6), Inches(4.35), Inches(6.5), Inches(2.6),
             "2. 全局「长辈大字版」适老模式（社会价值亮点）", C_AMBER, C_WHITE, C_AMBER_BD)
    add_bullets(s14, Inches(0.85), Inches(4.95), Inches(6.0), Inches(1.85), [
        ("● 一键高对比大字缩放：", "字号放大 1.3 倍、高对比配色、大点击热区，方便长辈阅读。", C_AMBER),
        ("● 口语词智能检索：", "直接搜“高血压、糖尿病、失眠”自动映射对应食养方剂。", C_GREEN_DARK),
    ], font_size=13.5, space_after=12)

    add_phone_mockup(s14, SHOT_DIR / "15-elder-home.png",
                     Inches(7.35), Inches(1.55), Inches(2.6), Inches(5.4), "实机：长辈高对比大字版", C_AMBER)
    add_phone_mockup(s14, SHOT_DIR / "10-openapi.png",
                     Inches(10.15), Inches(1.55), Inches(2.6), Inches(5.4), "实机：57路径 OpenAPI", C_BLUE)

    add_notes(s14, """【Slide 14 演讲稿（35 秒）】
工程上，我们将科研知识库设为严格只读挂载，全站 57 个路径通过了 106 项自动化单测，并打包了安卓 APK。
同时考虑到中老年群体是食养的核心受众，我们专门开发了一键“长辈大字模式”和慢病口语词检索，让老年用户也能轻松看清、放心使用。""")

    # =========================================================================
    # SLIDE 15: 现场演示动线与未来展望
    # =========================================================================
    s15 = prs.slides.add_slide(blank)
    add_bg(s15, page_num=15)
    add_header(s15, "14 · Live Demo & Roadmap", "现场实机演示动线与下一步科研演进",
               "四步实机交互直观展示可信度闭环，下一步拓展血浆蛋白结合率 (PPB) 预测", C_PURPLE, C_PURPLE_BG)

    sw, sh, sy = Inches(2.88), Inches(3.6), Inches(1.52)
    demo_steps = [
        ("① 白皮杉醇：红牌预警", SHOT_DIR / "12-compound-ad-out.png", "展示红色【应用域外】徽章", C_RED),
        ("② 落新妇苷：双模型对比", SHOT_DIR / "04-compound.png", "展示苷类成分双模型分歧提示", C_AMBER),
        ("③ 黄芩素：实验活性", SHOT_DIR / "13-compound-chembl.png", "展示 ChEMBL 36 靶点实测数据", C_GREEN),
        ("④ 茶罐配伍 & 长辈版", SHOT_DIR / "11-pantry.png", "勾选 5 味食材秒配可煮方", C_BLUE),
    ]
    for idx, (st_title, st_img, st_desc, st_col) in enumerate(demo_steps):
        sx = Inches(0.6) + idx * Inches(3.08)
        add_phone_mockup(s15, st_img, sx, sy, sw, sh, st_title, st_col)
        tb = s15.shapes.add_textbox(sx, sy + sh + Inches(0.05), sw, Inches(0.35))
        p = tb.text_frame.paragraphs[0]
        p.text = st_desc
        p.alignment = PP_ALIGN.CENTER
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = C_BODY

    add_card(s15, Inches(0.6), Inches(5.55), Inches(12.133), Inches(1.4),
             "下一步演进方向", C_BLUE, C_WHITE, C_BLUE_BD)
    add_bullets(s15, Inches(0.85), Inches(6.05), Inches(11.6), Inches(0.8), [
        ("● 拓展血浆蛋白结合率 (PPB) 预测：", "结合已整理的 3,921 条人体 PPB 实验数据，进一步预测入血后的游离有效成分比例。"),
        ("● 扩大真实用户可用性评测：", "面向校内外青年与长辈群体开展标准化 SUS 可用性量表验证与迭代优化。"),
    ], font_size=12.5, space_after=4)

    add_notes(s15, """【Slide 15 演讲稿（35 秒）】
在演示环节，我们可以通过四个页面快速展示系统亮点：白皮杉醇的应用域外预警、落新妇苷的双模型对比、黄芩素的 ChEMBL 实验数据，以及我的茶罐配伍和长辈版切换。
下一步，我们将引入 3,900 多条血浆蛋白结合率数据，继续探索入血后游离有效浓度的预测。""")

    # =========================================================================
    # SLIDE 16: 总结与致谢
    # =========================================================================
    s16 = prs.slides.add_slide(blank)
    add_bg(s16, page_num=16)

    add_card(s16, Inches(0.6), Inches(0.55), Inches(7.4), Inches(6.38), "", C_GREEN_DARK, C_WHITE, C_GREEN_BD)
    tb16 = s16.shapes.add_textbox(Inches(1.0), Inches(0.95), Inches(6.6), Inches(5.6))
    tf16 = tb16.text_frame
    tf16.word_wrap = True

    p = tf16.paragraphs[0]
    p.text = "SUMMARY & ACKNOWLEDGEMENTS"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = C_GREEN
    p.space_after = Pt(10)

    p = tf16.add_paragraph()
    p.text = "让中医药食同源：\n可知 · 可算 · 可信 · 可用"
    p.font.size = Pt(30)
    p.font.bold = True
    p.font.color.rgb = C_INK
    p.space_after = Pt(22)

    summary_points = [
        ("● 算法突破（可算）：\n", "构建 PU-Learning 入血预测模型 (AUC 0.903)，破解无负例难题。\n", C_BLUE),
        ("● 诚实闭环（可信）：\n", "首创「可信度四件套」与三档消融治理，守卫科研数据真实边界。\n", C_AMBER),
        ("● 普惠落地（可用）：\n", "覆盖 105 味药食同源全目录，打通端侧识方、茶罐配伍与长辈模式。\n", C_GREEN_DARK),
    ]
    for b_head, b_body, b_col in summary_points:
        p = tf16.add_paragraph()
        r1 = p.add_run()
        r1.text = b_head
        r1.font.bold = True
        r1.font.size = Pt(14.5)
        r1.font.color.rgb = b_col
        r2 = p.add_run()
        r2.text = b_body
        r2.font.size = Pt(13.5)
        r2.font.color.rgb = C_BODY
        p.space_after = Pt(12)

    p_end = tf16.add_paragraph()
    p_end.text = "衷心感谢指导老师与赵玉男教授团队！\n恳请各位评委专家批评指正！"
    p_end.font.size = Pt(14)
    p_end.font.bold = True
    p_end.font.color.rgb = C_INK

    add_phone_mockup(s16, SHOT_DIR / "09-assistant.png",
                     Inches(8.25), Inches(0.55), Inches(4.48), Inches(6.38),
                     "实机：「问青囊」寻证食养助手", C_GREEN)

    add_notes(s16, """【Slide 16 演讲稿（25 秒）】
总结来说，我们用 PU-Learning 解决入血预测难题，用可信度四件套守卫科学诚实，再用茶罐配伍和长辈模式服务大众日常健康，真正让药食同源做到“可知、可算、可信、可用”。
感谢各位评委老师，请老师们批评指正！""")

    prs.save(str(OUT_PATH))
    print(f"Minimalist presentation saved to: {OUT_PATH}")


if __name__ == "__main__":
    build_presentation()
