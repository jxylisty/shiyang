# -*- coding: utf-8 -*-
"""
生成《食养有据》挑战杯答辩 PPT (.pptx) —— 学术白底极简风（Clean Academic Light）升级版
特点：
1. 彻底摒弃压抑的黑底纯文字堆砌，采用顶会推崇的明亮学术白/暖米白底色 + 本草翡翠绿/算力天青蓝/严谨琥珀金视觉体系；
2. 16 页幻灯片每页均配备高分辨率视觉资产（画师定制封面插画、8 张 Retina 2x 实测数据图表与架构流图、11 张精准滚动的真机截图手机样机）；
3. 严格遵守 AGENTS.md 数据真实铁律，对齐 2026-11-06/07 最新实测数据与口径（105 味药材、6,205 化合物、4,562 入血预测、10,154 靶点、62,617 关联、73.9% 交叉验证一致率、食养科学三维评价指数）；
4. 每页内置完整、自然的演讲者逐字稿备注（Speaker Notes）。
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

# 明亮学术极简风调色盘 (Clean Academic Light)
C_BG = RGBColor(250, 248, 245)          # #FAF8F5 暖白学术宣纸底色
C_WHITE = RGBColor(255, 255, 255)       # #FFFFFF 纯白卡片底色
C_SOFT_GRAY = RGBColor(241, 245, 249)   # #F1F5F9 浅灰容器底色
C_BORDER = RGBColor(203, 213, 225)      # #CBD5E1 精致卡片边框

C_INK = RGBColor(15, 23, 42)            # #0F172A 石墨深黑主标题
C_BODY = RGBColor(51, 65, 85)           # #334155 正文深灰
C_MUTED = RGBColor(100, 116, 139)       # #64748B 辅助说明灰

C_GREEN = RGBColor(5, 150, 105)         # #059669 本草翡翠绿（主品牌色）
C_GREEN_DARK = RGBColor(6, 95, 70)      # #065F46 深本草绿
C_GREEN_BG = RGBColor(236, 253, 245)    # #ECFDF5 浅绿背景
C_GREEN_BD = RGBColor(110, 231, 183)    # #6EE7B7 浅绿边框

C_BLUE = RGBColor(29, 78, 216)          # #1D4ED8 算力天青蓝（算法主题色）
C_BLUE_BG = RGBColor(239, 246, 255)     # #EFF6FF 浅蓝背景
C_BLUE_BD = RGBColor(147, 197, 253)     # #93C5FD 浅蓝边框

C_AMBER = RGBColor(180, 83, 9)          # #B45309 严谨琥珀金（消融与证据主题色）
C_AMBER_BG = RGBColor(255, 251, 235)    # #FFFBEB 浅琥珀背景
C_AMBER_BD = RGBColor(252, 211, 77)     # #FCD34D 浅琥珀边框

C_RED = RGBColor(220, 38, 38)           # #DC2626 预警珊瑚红（适用域外红牌）
C_RED_BG = RGBColor(254, 242, 242)      # #FEF2F2 浅红背景
C_RED_BD = RGBColor(252, 165, 165)      # #FCA5A5 浅红边框

C_PURPLE = RGBColor(109, 40, 217)       # #6D28D9 交叉验证紫
C_PURPLE_BG = RGBColor(245, 243, 255)   # #F5F3FF 浅紫背景

DISCLAIMER_TEXT = "本平台内容为健康参考信息，不构成医疗建议，不用于诊断或治疗。"


def add_bg(slide, page_num: int = 0, total_pages: int = 16):
    """绘制暖白学术背景、顶部本草绿细装饰条与底部合规红线页脚"""
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = C_BG
    bg.line.fill.background()

    # 顶部双色学术装饰窄条
    top_bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(0.08))
    top_bar.fill.solid()
    top_bar.fill.fore_color.rgb = C_GREEN
    top_bar.line.fill.background()

    if page_num > 0:
        # 底部免责声明与页码栏
        tb = slide.shapes.add_textbox(Inches(0.6), Inches(7.12), Inches(12.133), Inches(0.3))
        tf = tb.text_frame
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.text = f"食养有据 (Shiyang) · 挑战杯学术科技作品答辩    |    红线声明：{DISCLAIMER_TEXT}    |    Page {page_num:02d} / {total_pages:02d}"
        p.font.size = Pt(9.5)
        p.font.color.rgb = C_MUTED


def add_header(slide, tag: str, title: str, subtitle: str = "", tag_color=C_GREEN, tag_bg=C_GREEN_BG):
    """标准白底学术风页眉：胶囊标签 + 主标题 + 副标题"""
    # 胶囊标签
    pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(0.28), Inches(2.5), Inches(0.32))
    pill.fill.solid()
    pill.fill.fore_color.rgb = tag_bg
    pill.line.color.rgb = tag_color
    pill.line.width = Pt(1)
    tf_p = pill.text_frame
    tf_p.margin_left = tf_p.margin_right = Inches(0.08)
    tf_p.margin_top = tf_p.margin_bottom = 0
    p0 = tf_p.paragraphs[0]
    p0.text = tag.upper()
    p0.alignment = PP_ALIGN.CENTER
    p0.font.size = Pt(9.5)
    p0.font.bold = True
    p0.font.color.rgb = tag_color

    # 标题与副标题
    tb = slide.shapes.add_textbox(Inches(0.6), Inches(0.64), Inches(12.133), Inches(0.82))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

    p1 = tf.paragraphs[0]
    p1.text = title
    p1.font.size = Pt(21)
    p1.font.bold = True
    p1.font.color.rgb = C_INK

    if subtitle:
        p2 = tf.add_paragraph()
        p2.text = subtitle
        p2.font.size = Pt(11.5)
        p2.font.color.rgb = C_MUTED
        p2.space_before = Pt(3)


def add_card(slide, left, top, width, height, title="", title_color=C_GREEN_DARK, bg_color=C_WHITE, border_color=C_BORDER):
    """绘制白底圆角学术卡片容器"""
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = bg_color
    shape.line.color.rgb = border_color
    shape.line.width = Pt(1.2)
    shape.adjustments[0] = 0.03

    if title:
        tb = slide.shapes.add_textbox(left + Inches(0.18), top + Inches(0.12), width - Inches(0.36), Inches(0.36))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.text = title
        p.font.size = Pt(13.5)
        p.font.bold = True
        p.font.color.rgb = title_color
    return shape


def add_bullets(slide, left, top, width, height, items, font_size=11.5, space_after=6):
    """向区域内写入结构化要点列表，支持 (bold_prefix, body_text, color) 三元组或纯字符串"""
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
    """按原始宽高比等比缩放居中置入图片，绝不拉伸变形，可选底部题注"""
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
        p.font.size = Pt(9.5)
        p.font.bold = True
        p.font.color.rgb = C_MUTED
    return pic


def add_phone_mockup(slide, img_path: Path, left, top, width, height, caption: str = "", badge_color=C_GREEN):
    """为移动端实机截图添加精致样机卡片边框与顶部说明"""
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
        p.font.size = Pt(10)
        p.font.bold = True
        p.font.color.rgb = badge_color
        img_top = top + Inches(0.34)
        img_h = height - Inches(0.42)
    else:
        img_top = top + Inches(0.08)
        img_h = height - Inches(0.16)

    add_picture_fit(slide, img_path, left + Inches(0.08), img_top, width - Inches(0.16), img_h)


def add_kpi_box(slide, left, top, width, height, num_str: str, label_str: str, sub_str: str, accent=C_GREEN, bg=C_WHITE):
    """绘制高视觉冲击力的核心数据指标卡"""
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    card.fill.solid()
    card.fill.fore_color.rgb = bg
    card.line.color.rgb = accent
    card.line.width = Pt(1.5)
    card.adjustments[0] = 0.06

    tb = slide.shapes.add_textbox(left + Inches(0.14), top + Inches(0.08), width - Inches(0.28), height - Inches(0.16))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

    p0 = tf.paragraphs[0]
    p0.text = num_str
    p0.font.size = Pt(20)
    p0.font.bold = True
    p0.font.color.rgb = accent

    p1 = tf.add_paragraph()
    p1.text = label_str
    p1.font.size = Pt(11)
    p1.font.bold = True
    p1.font.color.rgb = C_INK
    p1.space_before = Pt(2)

    p2 = tf.add_paragraph()
    p2.text = sub_str
    p2.font.size = Pt(9.5)
    p2.font.color.rgb = C_MUTED
    p2.space_before = Pt(1)


def add_notes(slide, notes_text: str):
    """写入演讲者逐字稿备注"""
    notes_slide = slide.notes_slide
    notes_slide.notes_text_frame.text = notes_text.strip()


def build_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # =========================================================================
    # SLIDE 01: 封面（明亮学术风 + 画师定制插画 + 核心实测指标卡 + 真机首屏）
    # =========================================================================
    s1 = prs.slides.add_slide(blank)
    add_bg(s1, page_num=1)

    # 左上竞赛徽标
    pill = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(0.45), Inches(3.6), Inches(0.38))
    pill.fill.solid()
    pill.fill.fore_color.rgb = C_GREEN_BG
    pill.line.color.rgb = C_GREEN
    p = pill.text_frame.paragraphs[0]
    p.text = "全国大学生「挑战杯」竞赛 · 学术科技作品答辩"
    p.alignment = PP_ALIGN.CENTER
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = C_GREEN_DARK

    # 主副标题
    tb1 = s1.shapes.add_textbox(Inches(0.6), Inches(0.98), Inches(6.6), Inches(2.1))
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    tf1.margin_left = tf1.margin_top = tf1.margin_right = tf1.margin_bottom = 0
    p = tf1.paragraphs[0]
    p.text = "食养有据 (Shiyang)"
    p.font.size = Pt(36)
    p.font.bold = True
    p.font.color.rgb = C_INK
    p.space_after = Pt(6)

    p2 = tf1.add_paragraph()
    p2.text = "基于 PU-Learning 入血预测与计算生物学机制的\n药食同源精准分析推荐平台"
    p2.font.size = Pt(16.5)
    p2.font.bold = True
    p2.font.color.rgb = C_GREEN_DARK
    p2.space_after = Pt(8)

    p3 = tf1.add_paragraph()
    p3.text = "从“经验食疗”走向“计算有据”——让每一杯日常食养茶饮都拥有可溯源的科学「成分说明书」"
    p3.font.size = Pt(11.5)
    p3.font.color.rgb = C_MUTED

    # 左侧 2x2 核心实测指标矩阵（2026-11-06 只读实测口径）
    kw, kh = Inches(3.15), Inches(1.18)
    add_kpi_box(s1, Inches(0.6), Inches(3.25), kw, kh, "105 味 / 73 方", "国家卫健委药食同源名录全覆盖", "双口径归属修复视图 · 经典茶饮汤羹", C_GREEN, C_WHITE)
    add_kpi_box(s1, Inches(3.95), Inches(3.25), kw, kh, "4,562 / 6,205", "化合物入血倾向预测三档覆盖", "ROC-AUC 0.903 · A类165 / B类795 / C类3,602", C_BLUE, C_WHITE)
    add_kpi_box(s1, Inches(0.6), Inches(4.58), kw, kh, "10,154 靶点", "62,617 条成分-靶点互作网络", "ChEMBL 465 条体外实测 · 127 条 L1 强证据", C_AMBER, C_WHITE)
    add_kpi_box(s1, Inches(3.95), Inches(4.58), kw, kh, "57 路径 / 61 端点", "FastAPI 毫秒级推断 + 端侧识方", "106 项单测全通过 · 适老大字版 + 安卓 APK", C_PURPLE, C_WHITE)

    # 左下团队与数据来源说明卡
    add_card(s1, Inches(0.6), Inches(5.92), Inches(6.5), Inches(1.05), "", bg_color=C_GREEN_BG, border_color=C_GREEN_BD)
    add_bullets(s1, Inches(0.78), Inches(6.02), Inches(6.15), Inches(0.9), [
        ("● 数据底座致谢：", "原始中药化学与移行成分数据由南京中医药大学赵玉男教授团队提供（ccTCM 2.0）", C_GREEN_DARK),
        ("● 申报团队工作：", "PU-Learning 建模验证、多口径治理、可信度四件套、端侧 OCR 纠偏与全栈产品化", C_INK),
    ], font_size=10.5, space_after=3)

    # 右侧：画师定制概念图 + 首页手机实机截图叠加展示
    add_card(s1, Inches(7.35), Inches(0.45), Inches(5.4), Inches(6.52), "从本草饮片 → 入血分子 → 蛋白靶点 → 循证决策", C_GREEN_DARK)
    add_picture_fit(s1, DIAG_DIR / "hero_cover_light.jpg", Inches(7.5), Inches(0.92), Inches(5.1), Inches(3.05),
                    "本草活性分子体内移行与蛋白受体网络计算生物学概念图")
    add_phone_mockup(s1, SHOT_DIR / "01-home.png", Inches(7.55), Inches(4.05), Inches(2.4), Inches(2.8), "实机首页：73方·6205成分", C_GREEN)
    add_phone_mockup(s1, SHOT_DIR / "audit_2026-11-07" / "t1_甘草_detail.png", Inches(10.15), Inches(4.05), Inches(2.4), Inches(2.8), "105 味药食同源全库", C_BLUE)

    add_notes(s1, """【Slide 01 演讲稿（约 30 秒）】
各位评委老师好！我是《食养有据》项目汇报人。
药食同源承载着我国数千年的食养智慧，但大众在日常喝养生茶、煲药膳汤时，长期面临三个核心追问：“里面到底有哪些活性成分？喝下去能不能进入血液循环？凭什么推荐给我？”
今天我们汇报的《食养有据》平台，基于南京中医药大学赵玉男教授团队提供的 ccTCM 2.0 原始数据底座，由我们团队构建了 PU-Learning 入血成分预测模型与可信度验证体系，完成了国家卫健委 105 味药食同源目录覆盖、6,205 个化合物收录、4,562 个分子三档入血预测与 10,154 个人类蛋白靶点映射，为每一道食养方案开具科学诚实的“有效成分说明书”。""")

    # =========================================================================
    # SLIDE 02: 立项背景与科学痛点（三栏对比 + 数据归属表 + 实机图）
    # =========================================================================
    s2 = prs.slides.add_slide(blank)
    add_bg(s2, page_num=2)
    add_header(s2, "01 · Background & Problem", "立项背景与核心科学问题：破除传统食疗「成分黑盒」",
               "直面传统食疗经验化、传统网络药理学假阳性泛滥与药代负样本缺失三大痛点")

    col_w = Inches(2.95)
    top_y = Inches(1.55)
    ch = Inches(3.55)

    # 痛点卡 1
    add_card(s2, Inches(0.6), top_y, col_w, ch, "痛点一：传统食疗「经验黑盒」", C_AMBER, C_AMBER_BG, C_AMBER_BD)
    add_bullets(s2, Inches(0.76), top_y + Inches(0.5), col_w - Inches(0.32), ch - Inches(0.6), [
        ("● 功效宣称缺乏分子依据：\n", "市面食疗产品多停留在古籍摘抄或概念营销，用户不知何种化学成分在起作用。", C_AMBER),
        ("● 剂量与暴露量脱节：\n", "茶包泡水喝下去到底能析出多少毫克有效成分？缺乏定量转移率区间参考。", C_AMBER),
        ("● 禁忌拦截缺失：\n", "体质偏颇相冲、孕哺及慢病人群忌口缺乏硬性安全剪枝规则。", C_AMBER),
    ], font_size=11, space_after=6)

    # 痛点卡 2
    add_card(s2, Inches(3.72), top_y, col_w, ch, "痛点二：传统网药「假阳性高」", C_RED, C_RED_BG, C_RED_BD)
    add_bullets(s2, Inches(3.88), top_y + Inches(0.5), col_w - Inches(0.32), ch - Inches(0.6), [
        ("● 忽视口服入血壁垒：\n", "传统网络药理学将药材全谱分子等权代入靶点富集，违背了「成分不入血就无法触达体内靶点」的药代规律。", C_RED),
        ("● 文献「无真实负例」困境：\n", "血中移行文献只报道「检出了什么」（正样本仅 13%），从不报道「什么没检出」。", C_RED),
        ("● 标准二分类器失效：\n", "直接把未标注分子当负例会造成严重的伪负样本惩罚。", C_RED),
    ], font_size=11, space_after=6)

    # 破局卡 3
    add_card(s2, Inches(6.84), top_y, col_w, ch, "破局：计算生物学 + 可信工程", C_GREEN_DARK, C_GREEN_BG, C_GREEN_BD)
    add_bullets(s2, Inches(7.0), top_y + Inches(0.5), col_w - Inches(0.32), ch - Inches(0.6), [
        ("● PU-Learning 入血预测：\n", "采用正样本-未标注（PU-Bagging）协议破译体内移行检出倾向（ROC-AUC 0.903）。", C_GREEN_DARK),
        ("● 可信度四件套防黑盒：\n", "留一法适用域标定 + ChEMBL 实测活性 + 4 算法族互验 + 三档暴露量区间。", C_GREEN_DARK),
        ("● 科研下放与端侧普惠：\n", "成分一句话科普卡、本地纯 CPU 识方纠偏、105 味茶罐配伍与长辈大字模式。", C_GREEN_DARK),
    ], font_size=11, space_after=6)

    # 底部：数据与方法归属边界卡（呼应 docs/模型说明与使用边界.md §一）
    add_card(s2, Inches(0.6), Inches(5.25), Inches(9.19), Inches(1.72), "学术诚信声明：原始数据来源与本团队研发工作边界（严格区分、绝不掠美）", C_BLUE, C_WHITE, C_BLUE_BD)
    add_bullets(s2, Inches(0.78), Inches(5.68), Inches(8.85), Inches(1.2), [
        ("● 赵玉男教授团队提供（ccTCM 2.0 原始库）：", "药材-成分-含量区间（6,196 行）、化合物基础信息与血中移行正例标识、成分-靶点关联（40,634 条）。", C_BLUE),
        ("● 申报团队独立完成（算法与工程全链路）：", "PU-Learning 模型训练与跨算法族独立验证、34→105 味扩容与双口径归属修复、prob_caliber 三档治理与消融实验、留一法全库适用域、ChEMBL 清洗挂链、食养科学三维评价指数及 57 路径全栈平台。", C_INK),
    ], font_size=10.5, space_after=4)

    # 右侧：方子详情页「成分一句话科普」实机截图
    add_phone_mockup(s2, SHOT_DIR / "audit_2026-11-07" / "t2_recipe1_sentence_card.png",
                     Inches(10.0), Inches(1.55), Inches(2.73), Inches(5.42), "实机：方子「成分一句话」科普卡", C_GREEN)

    add_notes(s2, """【Slide 02 演讲稿（约 45 秒）】
为什么我们要做这件事？
在应用端，传统食疗长期困在“经验黑盒”里，消费者不知道有效成分是什么、喝多少有意义；
而在科研端，传统网络药理学常被审稿人质疑“纸上谈兵”——因为它把药材里几百个成分不加筛选地等权拿去做靶点富集，忽略了“成分如果不进入血液循环，就难以到达全身靶点”这一药代动力学常识。
但要用机器学习预测入血，马上会遇到数据科学难题：实验文献只发表“在血浆里检出了哪些成分”，从来没人发表“哪些成分没检出”。正样本只占 13%，剩下的全是未标注样本。
为此，我们在南中医赵玉男老师团队提供的 ccTCM 2.0 原始数据基础上，独立完成了 PU-Learning 算法建模、105 味药食同源扩容治理、可信度四件套验证以及面向大众的全栈产品转化。""")

    # =========================================================================
    # SLIDE 03: 总体系统技术架构与核心算法全景（高清五层大图）
    # =========================================================================
    s3 = prs.slides.add_slide(blank)
    add_bg(s3, page_num=3)
    add_header(s3, "02 · System Architecture", "总体系统技术架构与五层算法工程全景",
               "从多组学数据底座、分子指纹表征、核心算法矩阵到多目标协同决策与适老终端的完整闭环", C_BLUE, C_BLUE_BG)

    add_picture_fit(s3, DIAG_DIR / "diagram_system_architecture.png",
                    Inches(0.55), Inches(1.48), Inches(12.23), Inches(5.55))

    add_notes(s3, """【Slide 03 演讲稿（约 45 秒）】
请看平台的五层总体架构图：
第一层是多组学数据底座，100% 覆盖国家卫健委 105 味药食同源目录，整合 ccTCM 2.0、ChEMBL 体外实测活性与 SymMap 本草词表，收录 6,205 个化合物、10,154 个蛋白靶点和 62,617 条互作关联；
第二层是特征工程层，利用 RDKit 提取 1024 位 Morgan 拓扑分子指纹与 19 维理化参数；
第三层是核心算法矩阵，涵盖 PU-Learning 入血预测、prob_caliber 三档口径治理、留一法全库适用域标定、UMAP 4,558 点化学空间流形降维，以及本地纯 CPU RapidOCR 与本草形近字纠错；
第四层与第五层向上支撑国标 CCMQ 67 题体质测评、安全禁忌硬剪枝、我的茶罐反向配伍、科学三维评价指数以及长辈高对比适老模式，后端通过 57 个 API 路径、61 个端点实现毫秒级响应。""")

    # =========================================================================
    # SLIDE 04: 算法核心一：PU-Learning 建模突破与生物学机理（高清流程图）
    # =========================================================================
    s4 = prs.slides.add_slide(blank)
    add_bg(s4, page_num=4)
    add_header(s4, "03 · Algorithm 01: PU-Learning", "算法核心一：PU-Learning 建模突破与「检出倾向 ≠ 吸收率」机理",
               "采用 Elkan-Noto PU-Bagging 协议消除未标注伪负例偏倚，深刻映射中药肠道菌群转化与一相代谢规律", C_BLUE, C_BLUE_BG)

    add_picture_fit(s4, DIAG_DIR / "diagram_algorithm_pulearning.png",
                    Inches(0.55), Inches(1.48), Inches(12.23), Inches(5.55))

    add_notes(s4, """【Slide 04 演讲稿（约 60 秒）】
下面重点汇报我们的第一个核心算法：PU-Learning 入血预测模型。
面对 282 个入血正样本与 1,887 个正负未知候选分子的 1:7 极端不平衡场景，我们采用 PU-Bagging 集成协议：在 30 轮迭代中，每轮保留全部正样本 P，从未标注池 U 中均匀随机抽取等量子集作为临时伪负例，结合 1024 位 Morgan 拓扑指纹与 19 维理化描述符训练多棵随机森林，再通过软投票平均抑制未标注池里的潜在正例噪声。
这里我们要向评委老师重点报告一个关键学术边界：模型预测的是“血中移行检出倾向”，而不是物理意义上的“口服生物利用度 F%”！
为什么这么说？看图下方两个真实案例：大分子人参皂苷 Re 分子量高达 947，违反 Lipinski 规则，直接透膜吸收率很低，但模型给出了 0.991 的高分——因为皂苷在肠道经菌群水解转化为次生苷后进入血液，在血浆 LC-MS 实验中检出率极高；相反，挥发性小分子石竹烯虽然极易透膜，但经过肝脏首过代谢极快清除，血浆很难捕到原型峰，所以得分仅 0.046。这证明模型学到的不是简单的分子量教条，而是真实的中药体内代谢检出规律！""")

    # =========================================================================
    # SLIDE 05: 算法核心二：模型实验评估与多口径预测治理（消融实验图）
    # =========================================================================
    s5 = prs.slides.add_slide(blank)
    add_bg(s5, page_num=5)
    add_header(s5, "04 · Algorithm 02: Ablation & Governance", "算法核心二：模型实验评估与 4,562 分子三档口径消融治理",
               "ROC-AUC 达 0.903±0.008；通过严谨消融实验证伪“缺维强推”，建立 prob_caliber 三级透明隔离", C_AMBER, C_AMBER_BG)

    # 顶部 4 个模型性能指标小卡
    mw = Inches(2.9)
    mh = Inches(0.95)
    add_kpi_box(s5, Inches(0.6), Inches(1.48), mw, mh, "0.903 ± 0.008", "测试集 ROC-AUC (3 Seeds)", "2,169 去重分子正负判别优秀", C_GREEN)
    add_kpi_box(s5, Inches(3.7), Inches(1.48), mw, mh, "0.573 ± 0.009", "测试集 PR-AUC (正例仅13%)", "最优 F1 = 0.585 · 召回率@0.5达91%", C_BLUE)
    add_kpi_box(s5, Inches(6.8), Inches(1.48), mw, mh, "prob ≥ 0.7", "平台工程高置信截断线", "精确率从 35.9% 跃升至 54.9%", C_AMBER)
    add_kpi_box(s5, Inches(9.9), Inches(1.48), mw, mh, "0.290 → 0.135", "消融实验外推误差减半", "否决缺维主模型(翻转率44.4%)", C_RED)

    # 下方高清消融与三档口径图
    add_picture_fit(s5, DIAG_DIR / "chart_ablation_caliber.png",
                    Inches(0.55), Inches(2.52), Inches(12.23), Inches(4.52))

    add_notes(s5, """【Slide 05 演讲稿（约 60 秒）】
在 3 随机种子交叉验证中，主模型取得了 0.903 的 ROC-AUC 和 0.573 的 PR-AUC。考虑到正样本仅占 13%，我们在工程展示端设定 prob ≥ 0.7 为高置信截断线，将精确率从默认阈值下的 35.9% 提升至 54.9%，作为成分排序参考。
更值得汇报的是：当我们将药材库从 34 味扩容到 105 味全名录、持 SMILES 分子扩至 4,562 个时，遇到了一个关键科学抉择——扩容出来的 3,602 个训练集外分子缺乏主模型所需的 7 个实验室实测 ADME 参数，能不能用中位数填补强行跑主模型？
我们没有盲目图省事，而是在 165 个已知成分上做了严格的消融实验（见右表）：如果强行虚拟填补跑 ccTCM 主模型，平均绝对偏差高达 0.290，阈值分类翻转率高达 44.4%，跟抛硬币差不多！而切换到仅依赖分子结构的 HERB 兜底模型，平均绝对偏差降至 0.135，一致率达 79%。
因此，我们在代码层通过 prob_caliber.py 建立了严格的三档互不重叠口径：A 类 165 个、B 类官方回填 795 个、C 类外推 3,602 个，并在前端用土黄色明确标注“外推估计”，对无结构分子诚实返回 None 绝不填 0。""")

    # =========================================================================
    # SLIDE 06: 算法鲁棒性：跨算法族独立交叉验证与分歧机理解构
    # =========================================================================
    s6 = prs.slides.add_slide(blank)
    add_bg(s6, page_num=6)
    add_header(s6, "05 · Algorithm 03: Cross-Validation", "算法鲁棒性：跨算法族独立交叉验证与 43 个分歧成分归因",
               "引入梯度提升树、神经网络与线性模型独立重训，一致率达 73.9% (122/165)，诚实解构分歧边界", C_PURPLE, C_PURPLE_BG)

    # 左侧：跨算法族图表
    add_picture_fit(s6, DIAG_DIR / "chart_cross_validation.png",
                    Inches(0.55), Inches(1.52), Inches(9.15), Inches(5.45))

    # 右侧：落新妇苷实机截图（展示琥珀色「主模型单独高」徽章）
    add_phone_mockup(s6, SHOT_DIR / "04-compound.png",
                     Inches(9.88), Inches(1.52), Inches(2.85), Inches(5.45),
                     "实机：落新妇苷「主模型单独高」", C_AMBER)

    add_notes(s6, """【Slide 06 演讲稿（约 45 秒）】
为了排除“预测结果只是随机森林特定算法巧合”的质疑，我们在同一数据集上用梯度提升树 XGBoost、多层感知机 MLP 和逻辑回归三个不同算法族进行了独立重训。
结果显示，独立 XGBoost 的 ROC-AUC 达到 0.8961，与主模型 0.903 高度接近，证明入血判别信号根植于分子拓扑结构本身。
在库内 165 个 A 类成分上，主模型与三独立模型均值的分类一致率达到 73.9%（122/165）。对于剩下的 43 个分歧成分，我们做了逐一结构排查：其中分子量大于 400 的大分子占 17 个、名称含“苷”的占 14 个（比如右图实机展示的落新妇苷，主模型 0.992、独立模型 0.0002）。这是因为主模型 PU 协议对未标注的大分子苷类更宽容，而独立模型采用标准二分类将未标注一律当负例惩罚。同时我们也诚实在文档中披露：其余少量小分子分歧尚未逐条完成湿实验解释，绝不夸大成“100%全解释”。""")

    # =========================================================================
    # SLIDE 07: 算法边界：基于留一法 LOO 的全库适用域量化与可信度四件套
    # =========================================================================
    s7 = prs.slides.add_slide(blank)
    add_bg(s7, page_num=7)
    add_header(s7, "06 · Algorithm 04: Applicability Domain", "算法边界：基于留一法 (LOO) 的全库适用域量化与可信度四件套",
               "计算与 2,437 训练集最大 Morgan Tanimoto 相似度，对超出能力边界的分子主动亮红牌预警", C_GREEN_DARK, C_GREEN_BG)

    add_picture_fit(s7, DIAG_DIR / "diagram_credibility_quartet.png",
                    Inches(0.55), Inches(1.52), Inches(9.15), Inches(5.45))

    add_phone_mockup(s7, SHOT_DIR / "12-compound-ad-out.png",
                     Inches(9.88), Inches(1.52), Inches(2.85), Inches(5.45),
                     "实机：白皮杉醇「应用域外」红牌", C_RED)

    add_notes(s7, """【Slide 07 演讲稿（约 45 秒）】
任何机器学习模型都有能力边界，走出训练集分布就会产生外推幻觉。为此，我们设计了留一法（Leave-One-Out）适用域量化算法。
为什么不用随机分子配对定阈值？因为化学空间很稀疏，随机配对的 5% 分位相似度只有 0.028，会把所有分子都包进域内，失去鉴别力。我们用留一法计算训练集每个分子离最近同伴的距离，精确标定出 5% 分位 0.333 为域外红线、25% 分位 0.582 为边缘黄线。
在 A 类 165 个成分中，域内 160 个、边缘 2 个、域外 3 个；推广到全库 4,558 个分子后，域内 2,775 个（60.9%）、边缘 1,193 个、域外 590 个。
如右图实机截图所示，当用户点开“白皮杉醇”（与训练集最大相似度仅 0.246），页面直接亮起红色的“应用域外·预测可靠性有限”徽章。适用域量化、ChEMBL 实测、跨算法互验与三档暴露量，共同构成了我们的“科学可信度四件套”。""")

    # =========================================================================
    # SLIDE 08: 拓扑表征：全库 4,558 分子 UMAP 高维化学空间流形
    # =========================================================================
    s8 = prs.slides.add_slide(blank)
    add_bg(s8, page_num=8)
    add_header(s8, "07 · Algorithm 05: Chemical Space UMAP", "拓扑表征：全库 4,558 分子 UMAP 高维化学空间拓扑流形",
               "将 1024 维 Morgan 指纹降维投影至二维连续流形，直观呈现骨架岛礁聚类与三档口径空间分布", C_BLUE, C_BLUE_BG)

    add_picture_fit(s8, DIAG_DIR / "chart_umap_manifold.png",
                    Inches(0.55), Inches(1.52), Inches(9.15), Inches(5.45))

    add_phone_mockup(s8, SHOT_DIR / "05-chem-map.png",
                     Inches(9.88), Inches(1.52), Inches(2.85), Inches(5.45),
                     "实机：/chem-map 三视图交互地图", C_BLUE)

    add_notes(s8, """【Slide 08 演讲稿（约 35 秒）】
为了让用户和科研人员直观看到这 4,558 个中药分子的全局结构关系，我们利用 UMAP 非线性流形算法（固定 random_state=42 保证完全可复现），将 1024 维指纹压缩至二维空间（见左图真实数据库坐标绘制的散点图与右图移动端实机界面）。
可以看到，黄酮类、皂苷类、挥发油单萜在流形上自发形成清晰的骨架岛礁，且深绿色的高入血概率分子呈现出明显的局部拓扑聚集；同时，3,598 个 C 类外推分子以土黄色底图诚实区分，支持按“入血概率、应用域、模型一致性”三种视角一键切换。""")

    # =========================================================================
    # SLIDE 09: 机制解析与评价升级：10,154 靶点、ChEMBL 实测与科学三维评价指数
    # =========================================================================
    s9 = prs.slides.add_slide(blank)
    add_bg(s9, page_num=9)
    add_header(s9, "08 · Mechanism & 3D Evaluation Index", "机制解析与评价升级：ChEMBL 实验锚定与「食养科学三维指数」",
               "补齐 465 条体外实测 Ki/IC50 证据环；将原呼吸课题受限评分重构为全库 73 方通用的科学三维指数", C_GREEN_DARK, C_GREEN_BG)

    add_picture_fit(s9, DIAG_DIR / "chart_target_3d_index.png",
                    Inches(0.55), Inches(1.52), Inches(9.15), Inches(5.45))

    add_phone_mockup(s9, SHOT_DIR / "13-compound-chembl.png",
                     Inches(9.88), Inches(1.52), Inches(2.85), Inches(5.45),
                     "实机：黄芩素 ChEMBL L1 强证据", C_GREEN)

    add_notes(s9, """【Slide 09 演讲稿（约 50 秒）】
入血之后，分子在体内如何起效？我们在 10,154 个人类蛋白靶点与 62,617 条互作网络基础上，完成了两项重要升级：
第一，补齐“体外实验实测”证据环：通过 InChIKey 精确对接欧洲生物信息研究所 ChEMBL 数据库，126 个成分精确命中，清洗入库 465 条人类单一蛋白靶点实测 Ki/IC50 记录，其中 127 条达到微摩尔级（pChEMBL ≥ 6）的 L1 强实验证据。清洗过程中我们专门攻克了老文献缺失 pChEMBL 自动换算、以及二次联查 target.json 剔除肿瘤细胞系污染两大难题（右图为黄芩素实机展示）。
第二，评价体系演进：原大创课题的“抗炎/免疫/气道修复”评分仅适用于护嗓呼吸类方剂，移植到食养全场景会水土不服。我们在 2026 年 11 月将其全面重构为覆盖全库 73 方的「食养科学三维评价指数」（eval_service.py）：即入血潜力（Top10 活性成分入血概率均值）、多靶协同（靶点连接数对数映射）与证据强度（融合 A 级药食同源/医籍与 B 级实验文献），实现了从单一课题向通用食养科学平台的跨越。""")

    # =========================================================================
    # SLIDE 10: 剂量模拟与科研下放：三档暴露量情景模型与大众科普转化
    # =========================================================================
    s10 = prs.slides.add_slide(blank)
    add_bg(s10, page_num=10)
    add_header(s10, "09 · Dose-Exposure & Popularization", "剂量模拟与科研下放：三档暴露量情景估算与 P0 科普转化",
               "遵循定量药理学 Fit-for-Purpose 原则“给诚实区间、不给假精度”；将硬核参数转化为大众秒懂的一句话卡", C_AMBER, C_AMBER_BG)

    # 左侧上下两张精炼卡片
    add_card(s10, Inches(0.6), Inches(1.52), Inches(6.6), Inches(2.75),
             "1. 定量暴露量三档情景模型（为什么不强建 PBPK 模型？）", C_AMBER, C_WHITE, C_AMBER_BD)
    add_bullets(s10, Inches(0.78), Inches(2.0), Inches(6.25), Inches(2.15), [
        ("● 暴露量区间公式：", "Exposure_i = 药材克重(g) × 文献含量区间[min, max] × 煎煮转移率 η_transfer", C_AMBER),
        ("● 三档转移率情景：", "摒弃单点常数，设 保守(η=0.3) / 基准(η=0.5) / 乐观(η=0.7) 三档，输出 [est_mg_min, est_mg_max] 数量级参考。", C_INK),
        ("● 方法学诚实边界：", "PBPK 生理药代模型虽是 FDA 金标准，但必须依赖每个单体的体内固有清除率(CLint)与血浆游离分数(fu)。天然产物普遍缺失此类实测值，强建 PBPK 等于参数伪造；Fit-for-Purpose 区间估算才是正统做法。", C_BODY),
    ], font_size=11, space_after=5)

    add_card(s10, Inches(0.6), Inches(4.42), Inches(6.6), Inches(2.55),
             "2. 科研功能对普通用户的下放（P0 三项落地 · Commit 30cc961）", C_GREEN_DARK, C_WHITE, C_GREEN_BD)
    add_bullets(s10, Inches(0.78), Inches(4.9), Inches(6.25), Inches(1.95), [
        ("● 方子页「成分一句话卡」：", "自动汇总“本方关联 14 个活性成分，排名前 6 里有 6 个喝后易在血中检出”，并附非吸收率/非疗效提示。", C_GREEN_DARK),
        ("● Lipinski 规则默认收起：", "成分页先给人话结论（“分子量 270 Da 小于 500 门槛，更容易穿肠入血”），参数细节一键展开，兼顾大众与专家。", C_BLUE),
        ("● 双模式无缝切换：", "提供 Pro 科研视图开关，大众看通俗结论与安全食养建议，医药评审看 SMILES、pChEMBL 与模型分歧。", C_INK),
    ], font_size=11, space_after=5)

    # 右侧两张手机实机图并排
    add_phone_mockup(s10, SHOT_DIR / "03-recipe-detail.png",
                     Inches(7.45), Inches(1.52), Inches(2.55), Inches(5.45),
                     "实机：银菊利咽茶通俗解读", C_GREEN)
    add_phone_mockup(s10, SHOT_DIR / "audit_2026-11-06" / "22_lipinski_expanded.png",
                     Inches(10.18), Inches(1.52), Inches(2.55), Inches(5.45),
                     "实机：Lipinski 人话特征解读", C_AMBER)

    add_notes(s10, """【Slide 10 演讲稿（约 40 秒）】
在剂量层面，用户常问“这杯茶喝下去到底有多少活性成分？”
如果有人声称对中药茶饮建了精确到小数点后两位的 PBPK 模型，那一定是伪造了清除率参数。我们遵循定量药理学 Fit-for-Purpose 原则，结合药材克重、ccTCM 文献含量区间以及保守 0.3、基准 0.5、乐观 0.7 三档煎煮转移率，输出诚实的毫克级摄入区间。
同时，为了让普通百姓看得懂硬核科研数据，我们落地了“科研下放 P0 方案”：在方子页提炼出“成分一句话结论卡”，在成分页将深奥的 Lipinski 五规则转化为通俗比喻并默认折叠参数细节，做到“外行看门道、内行看证据”。""")

    # =========================================================================
    # SLIDE 11: 端侧突破：本地轻量 RapidOCR 与本草形近字拓扑纠错算法
    # =========================================================================
    s11 = prs.slides.add_slide(blank)
    add_bg(s11, page_num=11)
    add_header(s11, "10 · Edge AI: RapidOCR & Typo Repair", "端侧突破：本地纯 CPU RapidOCR 与本草形近字拓扑纠错算法",
               "彻底摆脱云端视觉大模型 API 依赖，解决“OCR 认错一字导致整条靶点分析链路归零”的工程死穴", C_BLUE, C_BLUE_BG)

    # 左侧两张详细技术卡
    add_card(s11, Inches(0.6), Inches(1.52), Inches(4.45), Inches(5.45),
             "1. 本地轻量 RapidOCR 引擎 (ONNX)", C_BLUE, C_WHITE, C_BLUE_BD)
    add_bullets(s11, Inches(0.78), Inches(2.02), Inches(4.1), Inches(4.8), [
        ("● 为什么弃用生药外观拍照与云端大模型？\n", "干制切片饮片外观高度同质（黄芪片/甘草片极易混淆）；而拍方子文字再结合本草知识库才是高可靠路线。同时云端多模态 API 成本高、断网即瘫痪。", C_BLUE),
        ("● 纯 CPU 毫秒/秒级离线推理：\n", "基于 ONNX Runtime 本地部署 PP-OCRv4 轻量检测与识别模型，零 API 费用、断网可用。", C_INK),
        ("● 三档劣化合成图实测 100% 召回：\n",
         "• 清晰标准图：耗时 1.5s（药名 100% 识别）\n"
         "• 中度劣化图：耗时 3.6s（药名 100% 识别）\n"
         "• 极端劣化（倾斜+光照不均+高斯模糊+JPEG q35）：耗时 2.9s（100% 识别）", C_GREEN_DARK),
        ("● 行置信度剪枝：", "自动过滤 Conf < 0.5 的背景杂字噪点。", C_BODY),
    ], font_size=11, space_after=6)

    add_card(s11, Inches(5.22), Inches(1.52), Inches(4.45), Inches(5.45),
             "2. 本草形近字拓扑纠错 (correct_herb_name)", C_PURPLE, C_WHITE, C_BORDER)
    add_bullets(s11, Inches(5.4), Inches(2.02), Inches(4.1), Inches(4.8), [
        ("● 致命痛点：\n", "OCR 常把「金银花」认成「金银化」、「枸杞」认成「枸札」——错一字会导致后续成分与靶点查询整条链路归零！", C_RED),
        ("● 三级受限本草纠偏策略（基于 105 味药食同源 + 703 味 SymMap 词表）：\n",
         "① 第一级（同长度形近字表替换）：\n    如「金银化 → 金银花」、「甘苹 → 甘草」\n"
         "② 第二级（受限省字补全匹配）：\n    如「枸札 → 枸杞子」、「决明 → 决明子」\n"
         "③ 第三级（编辑距离=1 受限匹配）：\n    如「阵皮 → 陈皮」，须满足单字重叠约束", C_PURPLE),
        ("● 安全防误伤锁（宁可不纠、绝不乱猜）：\n", "多候选歧义直接拒猜；纯编辑距离无形近依据拒猜（如「桂圆」绝不误纠为「桂枝」）。", C_AMBER),
        ("★ 实测硬指标：", "错字纠错率 11/12 (91.7%)，真药名误纠率 0/40 (0.0%)！前端全透明展示纠偏轨迹。", C_GREEN_DARK),
    ], font_size=10.8, space_after=5)

    # 右侧：自定义鉴方真机截图（再也不是 404！）
    add_phone_mockup(s11, SHOT_DIR / "14-custom-recipe.png",
                     Inches(9.88), Inches(1.52), Inches(2.85), Inches(5.45),
                     "实机：自定义鉴方与形近字识方", C_PURPLE)

    add_notes(s11, """【Slide 11 演讲稿（约 45 秒）】
在实际落地中，用户拿到一张养生帖或纸质方子想查成分，手输太麻烦，而通用 OCR 经常把“金银花”认成“金银化”、“枸杞”认成“枸札”、“陈皮”认成“阵皮”。在数据库查询里，错一个字就意味着整味药的成分和靶点全部归零！
为此，我们没有依赖昂贵且有幻觉的云端多模态大模型，而是自研了“本地纯 CPU RapidOCR + 本草形近字拓扑纠错算法（correct_herb_name）”。
基于 105 味药食同源与 703 味 SymMap 本草词表，我们设计了同长度形近替换、受限省字补全、受限编辑距离三级纠偏，并加上严格的防歧义安全锁（比如绝不把词表外的桂圆瞎猜成桂枝）。实测错字纠正率达 11/12，而对 40 个真实药名的误伤率是 0/40！纯 CPU 断网可用，前端还会把“已将金银化自动纠正为金银花”透明展示给用户。""")

    # =========================================================================
    # SLIDE 12: 落地功能：我的茶罐反向图配伍与多方对比实验室
    # =========================================================================
    s12 = prs.slides.add_slide(blank)
    add_bg(s12, page_num=12)
    add_header(s12, "11 · Core Applications: Pantry & Compare Lab", "落地应用：我的茶罐子集图覆盖反向配伍与多方对比实验室",
               "解决年轻人“办公桌囤了一罐枸杞菊花陈皮却不知怎么搭”与“两个类似方子不知选哪个”的真实场景", C_GREEN_DARK, C_GREEN_BG)

    # 左侧功能算法卡
    add_card(s12, Inches(0.6), Inches(1.52), Inches(6.5), Inches(2.65),
             "1. 【我的茶罐】食材子集图覆盖贪心算法 (Pantry Matcher)", C_GREEN_DARK, C_WHITE, C_GREEN_BD)
    add_bullets(s12, Inches(0.78), Inches(2.0), Inches(6.15), Inches(2.05), [
        ("● 范式反转（从“按方抓药”到“翻罐组方”）：\n", "五大语义抽屉（花叶果茶/根茎本草/谷豆果仁/生鲜煲汤/糖蜜茶奶）叠加家常异名映射（搜“桂圆”命中“龙眼肉”、搜“淮山”命中“山药”）。", C_GREEN_DARK),
        ("● 子集图覆盖数学模型：", "Coverage(r) = |M_owned ∩ M_required(r)| / |M_required(r)|（自动剔除冰糖/蜂蜜等辅料干扰）。", C_BLUE),
        ("● 三级字典序贪心排序：", "① 覆盖率降序（今晚直接能煮）→ ② 缺料数升序（差一味好凑齐）→ ③ 高入血活性成分数降序。", C_INK),
    ], font_size=11, space_after=5)

    add_card(s12, Inches(0.6), Inches(4.32), Inches(6.5), Inches(2.65),
             "2. 【对比实验室】多方并排 PK 与自定义鉴方 (Compare Lab)", C_AMBER, C_WHITE, C_AMBER_BD)
    add_bullets(s12, Inches(0.78), Inches(4.8), Inches(6.15), Inches(2.05), [
        ("● 双槽位并排深度比对：\n", "支持任意两首食疗方（如「银菊利咽茶 vs 麦冬金银花茶」）同屏比对共有配料、独有配料、高入血成分重合度及生物靶点通路差异。", C_AMBER),
        ("● 全站多入口一键联动：\n", "方子详情页、为你推荐卡、搜索结果页均设「对比此方」快捷槽位，移动端采用 computed 布尔桥接抽屉丝滑选方。", C_INK),
        ("● 自定义鉴方无缝打通：\n", "哪怕是不在 73 首经典库里的民间自拟方，也能在茶罐第二标签页调用 HERB/ccTCM 实时算出成分与靶点证据。", C_BLUE),
    ], font_size=11, space_after=5)

    # 右侧两张真机截图：茶罐已选 5 味 + 对比实验室双方比对
    add_phone_mockup(s12, SHOT_DIR / "11-pantry.png",
                     Inches(7.35), Inches(1.52), Inches(2.6), Inches(5.45),
                     "实机：已入罐5味→直接能煮2道", C_GREEN)
    add_phone_mockup(s12, SHOT_DIR / "08-compare.png",
                     Inches(10.15), Inches(1.52), Inches(2.6), Inches(5.45),
                     "实机：银菊茶 vs 麦冬金银花茶", C_AMBER)

    add_notes(s12, """【Slide 12 演讲稿（约 45 秒）】
在用户高频场景上，我们重点打磨了“我的茶罐”和“对比实验室”两大杀手级功能（请看右侧两张真机运行截图）。
很多年轻人在办公室囤了陈皮、枸杞、麦冬、菊花，却不知道手头这几味料今晚能煮什么。在“我的茶罐”中，用户只需点选已有的 5 味食材，后端基于子集图覆盖贪心算法，毫秒级滤除辅料干扰，按“覆盖率降序、缺料数升序、高入血成分数降序”立刻给出“今晚直接能煮 2 道、差一味可凑 8 道”的精准方案；
而在“对比实验室”中，用户可以将“银菊利咽茶”与“麦冬金银花茶”并排 PK，直观对比两者的配料差异、入血成分覆盖与靶点通路，选方不再盲目。""")

    # =========================================================================
    # SLIDE 13: 推荐引擎：国标 CCMQ 67 题体质量表与安全剪枝多目标协同
    # =========================================================================
    s13 = prs.slides.add_slide(blank)
    add_bg(s13, page_num=13)
    add_header(s13, "12 · Multi-Objective Recommendation", "推荐引擎：国标 CCMQ 67 题体质辨识与 Safety Gate 安全剪枝",
               "将中华中医药学会标准量表、红线禁忌一票否决剪枝与 24 节气时令/入血丰度融入统一决策流", C_BLUE, C_BLUE_BG)

    # 左侧：上方放业务决策流大图，下方放公式与安全剪枝说明
    add_picture_fit(s13, DIAG_DIR / "diagram_pantry_recommendation.png",
                    Inches(0.55), Inches(1.52), Inches(9.15), Inches(3.25))

    add_card(s13, Inches(0.6), Inches(4.88), Inches(9.05), Inches(2.08),
             "安全红线优先于推荐打分：Safety Gate 剪枝 + 四维协同效用函数", C_GREEN_DARK, C_WHITE, C_GREEN_BD)
    add_bullets(s13, Inches(0.78), Inches(5.34), Inches(8.7), Inches(1.5), [
        ("● 第一步（Safety Gate 硬约束剪枝）：", "基于 safety_service.py 规则库，对孕妇/哺乳期/儿童/慢病禁忌及主导体质相冲（如阴虚火旺忌温燥、脾胃虚寒忌苦寒）执行一票否决拦截，并支持家庭成员档案（family_member 表）切换。", C_RED),
        ("● 第二步（四维协同打分）：", "S(r) = w_c·Match(体质适宜) + w_t·SolarTerm(24节气当令主题) + w_b·Behavior(收藏打卡隐式偏好) + w_a·BloodRatio(高入血成分丰度)，每条推荐均输出可解释的推荐理由标签。", C_INK),
    ], font_size=10.8, space_after=5)

    # 右侧：CCMQ 67 题体质量表实机截图
    add_phone_mockup(s13, SHOT_DIR / "06-quiz.png",
                     Inches(9.88), Inches(1.52), Inches(2.85), Inches(5.45),
                     "实机：CCMQ 67 题国标体质测评", C_BLUE)

    add_notes(s13, """【Slide 13 演讲稿（约 35 秒）】
在个性化推荐引擎上，我们坚持“安全第一、有据可依”。
系统完整内置了中华中医药学会标准的 CCMQ 67 题九种体质量表（见右图实机界面），并支持为父母、伴侣建立独立的家庭成员体质档案。
在推荐计算时，第一道防线是 Safety Gate 安全剪枝：凡是触发体质相冲或孕哺慢病禁忌的方子，直接一票否决拦截；通过安全门的候选方，再综合体质匹配度、24 节气当令食养主题、用户打卡偏好以及方子高入血成分丰度进行四维加权排序。""")

    # =========================================================================
    # SLIDE 14: 全栈工程落地与长辈高对比大字适老无障碍模式
    # =========================================================================
    s14 = prs.slides.add_slide(blank)
    add_bg(s14, page_num=14)
    add_header(s14, "13 · Engineering & Elder Accessibility", "全栈工程高可用架构与长辈高对比大字适老无障碍模式",
               "57 路径 / 61 端点 · 106 项自动化单测全通过 · 双库动静物理隔离 · 科技向善消除银发数字鸿沟", C_GREEN_DARK, C_GREEN_BG)

    add_card(s14, Inches(0.6), Inches(1.52), Inches(6.5), Inches(2.65),
             "1. 工业级全栈工程与数据只读防篡改设计", C_BLUE, C_WHITE, C_BLUE_BD)
    add_bullets(s14, Inches(0.78), Inches(2.0), Inches(6.15), Inches(2.05), [
        ("● 双 SQLite 动静物理隔离：\n", "科研知识库 shiyang.db (16.5MB, 22张表) 运行时以 URI mode=ro 严格只读挂载，从根源杜绝任何接口误写污染；用户库 user.db 开启 WAL 并发模式承载收藏、打卡与家庭档案。", C_BLUE),
        ("● 57 路径 / 61 端点 + 106 项单测全绿：\n", "涵盖 10 个测试模块 106 条 pytest 自动化用例（7.2s 全通过），另有 19 步从零确定性重建链路（rebuild_all.py）与 Wikimedia 146 张配料图 CC 署名审计。", C_INK),
        ("● 多端交付：", "支持 Web 端、局域网扫码体验及 Capacitor 打包原生 Android APK（v2.0.0 挑战杯版）。", C_GREEN_DARK),
    ], font_size=10.8, space_after=5)

    add_card(s14, Inches(0.6), Inches(4.32), Inches(6.5), Inches(2.65),
             "2. 全局「长辈版」高对比大字适老无障碍模式（社会价值亮点）", C_AMBER, C_WHITE, C_AMBER_BD)
    add_bullets(s14, Inches(0.78), Inches(4.8), Inches(6.15), Inches(2.05), [
        ("● 直击银发群体痛点：\n", "药食同源最核心的受众是中老年慢病调理人群，但传统健康 App 字小色淡、层级深，老人“看不清、点不准”。", C_AMBER),
        ("● 全局 html.elder-mode 令牌注入：\n", "顶栏一键切换「An 长辈版」，正文与标题动态放大 1.25~1.35 倍，字重加粗，卡片对比度提升至 WCAG AAA 级，全部可点击触控热区强制 ≥ 48px，且状态持久化保存。", C_INK),
        ("● 口语化疾病检索扩展：", "老人搜“高血压、糖尿病、失眠、上火”等口语词，自动映射至眩晕、消渴、不寐等本草功效词。", C_GREEN_DARK),
    ], font_size=10.8, space_after=5)

    # 右侧：长辈版首页 vs OpenAPI 57 路径实机图
    add_phone_mockup(s14, SHOT_DIR / "15-elder-home.png",
                     Inches(7.35), Inches(1.52), Inches(2.6), Inches(5.45),
                     "实机：一键切换「长辈大字版」", C_AMBER)
    add_phone_mockup(s14, SHOT_DIR / "10-openapi.png",
                     Inches(10.15), Inches(1.52), Inches(2.6), Inches(5.45),
                     "实机：57路径/61端点 OpenAPI", C_BLUE)

    add_notes(s14, """【Slide 14 演讲稿（约 40 秒）】
扎实的算法需要可靠的工程承载。系统后端采用双 SQLite 物理隔离：16.5MB 的科研知识库以只读模式（mode=ro）挂载，确保运行时科研数据绝对零篡改；全站 57 个路径、61 个端点均通过了 106 项自动化单元测试，并已完成 Android APK 原生打包。
更有人文温度的是，考虑到药食同源大量服务于中老年群体，我们研发了全局“长辈大字高对比适老模式”（见右图实机画面），一键放大全站字号与触控热区，并支持直接用“高血压、糖尿病、失眠”等口语词检索食养方，让前沿计算生物学成果真正跨越银发数字鸿沟。""")

    # =========================================================================
    # SLIDE 15: 现场 3 分钟实机演示动线与在研演进路线图（四步连环画）
    # =========================================================================
    s15 = prs.slides.add_slide(blank)
    add_bg(s15, page_num=15)
    add_header(s15, "14 · Live Demo & Future Roadmap", "现场 3 分钟实机演示动线与下一步科研演进路线",
               "用真实在线运行系统的 4 个代表性切面回答“预测凭什么可信”，并规划 PPB 血浆蛋白结合率演进", C_PURPLE, C_PURPLE_BG)

    # 上半部分：4 张实机演示步骤卡横排
    sw = Inches(2.88)
    sh = Inches(3.45)
    sy = Inches(1.52)
    demo_steps = [
        ("STEP 1 · 主动亮出算法边界", SHOT_DIR / "12-compound-ad-out.png", "点开「白皮杉醇」：看红色【应用域外】徽章(Sim=0.246)，证明不搞盲目外推", C_RED),
        ("STEP 2 · 解构双模型分歧", SHOT_DIR / "04-compound.png", "点开「落新妇苷」：看琥珀色【主模型单独高】徽章，解释苷类菌群水解机理", C_AMBER),
        ("STEP 3 · 国际实验数据背书", SHOT_DIR / "13-compound-chembl.png", "点开「黄芩素」：看 ChEMBL 36 靶点实测 Ki/IC50 与 L1 强证据勋章", C_GREEN),
        ("STEP 4 · 翻茶罐与长辈关怀", SHOT_DIR / "11-pantry.png", "勾选 5 味食材秒配可煮方 + 一键切换【长辈大字版】展示全栈落地度", C_BLUE),
    ]
    for idx, (st_title, st_img, st_desc, st_col) in enumerate(demo_steps):
        sx = Inches(0.6) + idx * Inches(3.08)
        add_phone_mockup(s15, st_img, sx, sy, sw, sh, st_title, st_col)
        tb = s15.shapes.add_textbox(sx, sy + sh + Inches(0.04), sw, Inches(0.48))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.text = st_desc
        p.font.size = Pt(9.5)
        p.font.bold = True
        p.font.color.rgb = C_BODY

    # 下半部分：下一步科研与工程演进路线图
    add_card(s15, Inches(0.6), Inches(5.55), Inches(12.133), Inches(1.42),
             "下一步在研演进路线（诚实面对现有局限，持续深化计算药理学链条）", C_BLUE, C_WHITE, C_BLUE_BD)
    add_bullets(s15, Inches(0.78), Inches(6.0), Inches(11.75), Inches(0.9), [
        ("① 引入 3,921 条人体血浆蛋白结合率 (PPB) 实测数据：", "已评估 AutoMolDesigner 附带数据集（3,921 条 PPB + 668 条 HIA），下一步训练 PPB 预测子模型，打通「入血 → 游离未结合有效浓度 (fu)」链条。", C_BLUE),
        ("② 完善独立验证预处理与湿实验对齐：", "将独立验证脚本的中位数填补严格限制在各折训练集内，并对尚未解释的小分子分歧开展文献/实验复核。", C_AMBER),
        ("③ 开展 30 人真实用户可用性评测 (SUS)：", "依照《用户验证方案.md》执行标准化任务完成率与 SUS 量表回收，沉淀真实用户实证。", C_GREEN_DARK),
    ], font_size=10.5, space_after=3)

    add_notes(s15, """【Slide 15 演讲稿（约 40 秒）】
如果评委老师在提问环节需要查看实机演示，我们准备了 3 分钟一镜到底的演示动线：
第一步点开“白皮杉醇”，看红色应用域外预警，展示我们主动承认模型局限的诚实态度；
第二步点开“落新妇苷”，看双模型对比与琥珀色分歧徽章，验证苷类代谢机理；
第三步点开“黄芩素”，查看欧洲 ChEMBL 数据库的 36 个靶点体外实测活性；
第四步在“我的茶罐”勾选 5 味家常食材秒出配伍，并一键切换长辈大字版。
展望下一步，我们已经完成了对 3,921 条人体血浆蛋白结合率（PPB）实测数据的清洗评估，即将引入游离药物分数预测，进一步打通从“入血”到“游离起效”的生物物理闭环。""")

    # =========================================================================
    # SLIDE 16: 总结与致谢（升华主旨 + 问青囊实机 + 概念插画）
    # =========================================================================
    s16 = prs.slides.add_slide(blank)
    add_bg(s16, page_num=16)

    # 左侧总结大卡
    add_card(s16, Inches(0.6), Inches(0.55), Inches(7.4), Inches(6.38), "", C_GREEN_DARK, C_WHITE, C_GREEN_BD)
    tb16 = s16.shapes.add_textbox(Inches(0.95), Inches(0.85), Inches(6.7), Inches(5.8))
    tf16 = tb16.text_frame
    tf16.word_wrap = True
    tf16.margin_left = tf16.margin_top = tf16.margin_right = tf16.margin_bottom = 0

    p = tf16.paragraphs[0]
    p.text = "SUMMARY & ACKNOWLEDGEMENTS"
    p.font.size = Pt(12)
    p.font.bold = True
    p.font.color.rgb = C_GREEN
    p.space_after = Pt(8)

    p = tf16.add_paragraph()
    p.text = "让中医药食同源：\n可知 · 可算 · 可信 · 可用"
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = C_INK
    p.space_after = Pt(16)

    summary_points = [
        ("● 一、算法突破（可算）：\n", "针对中药血中移行数据“正例仅 13%、缺失真负例”痛点，构建 PU-Bagging 入血预测模型（ROC-AUC 0.903），科学阐明“血中检出倾向 ≠ 口服吸收率”。\n", C_BLUE),
        ("● 二、可信闭环（可信）：\n", "首创药食同源「可信度四件套」与 prob_caliber 三档消融治理（4,562 分子），用留一法适用域、ChEMBL 465 条实验活性、4 算法族互验与三档暴露量守卫学术诚实。\n", C_AMBER),
        ("● 三、普惠工程（可用）：\n", "100% 覆盖卫健委 105 味名录，重构「食养科学三维评价指数」，自研端侧纯 CPU RapidOCR 与本草形近字纠错（纠错 11/12、误纠 0/40），上线茶罐配伍与长辈适老模式。\n", C_GREEN_DARK),
    ]
    for b_head, b_body, b_col in summary_points:
        p = tf16.add_paragraph()
        r1 = p.add_run()
        r1.text = b_head
        r1.font.bold = True
        r1.font.size = Pt(12.5)
        r1.font.color.rgb = b_col
        r2 = p.add_run()
        r2.text = b_body
        r2.font.size = Pt(11.5)
        r2.font.color.rgb = C_BODY
        p.space_after = Pt(8)

    p_end = tf16.add_paragraph()
    p_end.text = "“可信的本质不是每个数字都完美，而是每个数字都诚实。”\n衷心感谢指导老师与赵玉男教授团队！恳请各位评委专家批评指正！"
    p_end.font.size = Pt(12.5)
    p_end.font.bold = True
    p_end.font.color.rgb = C_INK

    # 右侧：问青囊寻证助手实机图 + 概念图呼应
    add_phone_mockup(s16, SHOT_DIR / "09-assistant.png",
                     Inches(8.25), Inches(0.55), Inches(4.48), Inches(6.38),
                     "实机：「问青囊」寻证食养助手", C_GREEN)

    add_notes(s16, """【Slide 16 演讲稿（约 30 秒）】
最后总结我们的工作：
评测一个科学计算与健康推荐系统的价值，看的不只是它的 ROC 曲线有多高，更是看它敢不敢把自己的不可靠之处亮出来。
我们用 PU-Learning 破译入血规律，用消融实验和可信度四件套守卫数据诚实，用端侧纠错、茶罐配伍和长辈模式践行科技向善，真正让药食同源做到“可知、可算、可信、可用”。
食养有据，诚实有据！我的汇报完毕，恳请各位评委老师批评指正！""")

    prs.save(str(OUT_PATH))
    print(f"Presentation saved successfully to: {OUT_PATH}")


if __name__ == "__main__":
    build_presentation()
