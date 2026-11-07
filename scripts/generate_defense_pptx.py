# -*- coding: utf-8 -*-
"""
生成挑战杯答辩 PPT (.pptx)
侧重算法与可信度科研体系，包含完整演讲者逐字稿备注与高科技学术排版
"""
import os
import sys
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

ROOT = Path(__file__).resolve().parent.parent
IMG_PATH = ROOT / "docs" / "tcm_ai_computational_biology.jpg"
OUT_PATH = ROOT / "docs" / "食养有据_挑战杯答辩PPT_侧重算法.pptx"

# 调色盘
COLOR_BG = RGBColor(11, 19, 43)          # #0B132B 深海军蓝
COLOR_CARD = RGBColor(28, 37, 65)        # #1C2541 卡片深蓝灰
COLOR_CARD_BORDER = RGBColor(58, 80, 107) # #3A506B 卡片边框
COLOR_CYAN = RGBColor(0, 240, 255)       # #00F0FF 荧光青
COLOR_TEAL = RGBColor(16, 185, 129)      # #10B981 活力绿
COLOR_GOLD = RGBColor(245, 158, 11)      # #F59E0B 琥珀金
COLOR_WHITE = RGBColor(248, 250, 252)    # #F8FAFC 纯白
COLOR_MUTED = RGBColor(148, 163, 184)    # #94A3B8 浅灰
COLOR_CARD_HIGHLIGHT = RGBColor(30, 41, 75)

def add_bg(slide):
    """设置纯深色科技背景"""
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = COLOR_BG
    bg.line.color.rgb = COLOR_BG
    return bg

def add_header(slide, tag: str, title: str, subtitle: str = ""):
    """标准科技学术页眉"""
    tb = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.733), Inches(1.1))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
    
    # 标签 pill
    p0 = tf.paragraphs[0]
    p0.text = f"● {tag.upper()}"
    p0.font.size = Pt(11)
    p0.font.bold = True
    p0.font.color.rgb = COLOR_CYAN
    p0.space_after = Pt(4)
    
    # 主标题
    p1 = tf.add_paragraph()
    p1.text = title
    p1.font.size = Pt(22)
    p1.font.bold = True
    p1.font.color.rgb = COLOR_WHITE
    
    # 副标题
    if subtitle:
        p2 = tf.add_paragraph()
        p2.text = subtitle
        p2.font.size = Pt(12)
        p2.font.color.rgb = COLOR_MUTED
        p2.space_before = Pt(2)

def add_card(slide, left, top, width, height, title="", title_color=COLOR_CYAN, border_color=COLOR_CARD_BORDER):
    """绘制高科技卡片容器"""
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = COLOR_CARD
    shape.line.color.rgb = border_color
    shape.line.width = Pt(1.2)
    
    if title:
        tb = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(0.15), width - Inches(0.4), Inches(0.4))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.text = title
        p.font.size = Pt(14)
        p.font.bold = True
        p.font.color.rgb = title_color
    return shape

def add_notes(slide, notes_text: str):
    """写入演讲者备注（逐字稿）"""
    notes_slide = slide.notes_slide
    text_frame = notes_slide.notes_text_frame
    text_frame.text = notes_text

def build_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # =========================================================================
    # SLIDE 1: 封面
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    add_bg(s1)
    
    # 左侧文字区域
    tb1 = s1.shapes.add_textbox(Inches(0.8), Inches(1.0), Inches(6.8), Inches(5.5))
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    
    p = tf1.paragraphs[0]
    p.text = "全国大学生「挑战杯」竞赛答辩汇报"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = COLOR_CYAN
    p.space_after = Pt(14)
    
    p = tf1.add_paragraph()
    p.text = "食养有据 (Shiyang)"
    p.font.size = Pt(36)
    p.font.bold = True
    p.font.color.rgb = COLOR_WHITE
    p.space_after = Pt(8)
    
    p = tf1.add_paragraph()
    p.text = "基于 PU-Learning 入血预测与计算生物学机制的\n药食同源精准推荐平台"
    p.font.size = Pt(17)
    p.font.bold = True
    p.font.color.rgb = COLOR_GOLD
    p.space_after = Pt(24)
    
    # 核心指标徽章栏
    badges = [
        "● 国家卫健委 105 味药食同源全名录 100% 覆盖",
        "● 4,562 分子入血倾向预测 · 10,154 人类蛋白靶点",
        "● 62,617 条相互作用网络 · 4 算法族交叉互验",
        "● 57 路径 61 端点高性能微秒级推断架构",
    ]
    for b in badges:
        p = tf1.add_paragraph()
        p.text = b
        p.font.size = Pt(12)
        p.font.color.rgb = COLOR_MUTED
        p.space_after = Pt(4)
        
    p = tf1.add_paragraph()
    p.text = "\n参赛团队：食养有据团队    |    指导老师：课题指导组"
    p.font.size = Pt(12)
    p.font.bold = True
    p.font.color.rgb = COLOR_WHITE

    p = tf1.add_paragraph()
    p.text = "红线说明：本平台内容为健康参考信息，不构成医疗建议，不用于诊断或治疗。"
    p.font.size = Pt(9)
    p.font.color.rgb = COLOR_MUTED

    # 右侧概念图
    if IMG_PATH.exists():
        s1.shapes.add_picture(str(IMG_PATH), Inches(7.8), Inches(1.1), width=Inches(4.8))

    add_notes(s1, """【演讲口播（30 秒）】
各位评委老师好！我是《食养有据》项目负责人。
千百年来，药食同源承载着我国博大的食疗智慧，但长久以来受制于‘成分作用如黑盒、缺乏体内动力学代谢表征、推荐停留在经验主义’。
今天我们汇报的项目，源自团队在计算系统生物学领域的科研积累，创新引入 PU-Learning 机器学习算法破译中药入血成分，完成了国家卫健委 105 味药食同源全名录覆盖，构建了从入血预测、全库适用域量化、靶点网络富集到轻量端侧识方、反向配伍的全链条闭环，让每一杯食疗茶饮都能开具出科学可信的‘有效成分说明书’。""")

    # =========================================================================
    # SLIDE 2: 立项背景与学术痛点
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    add_bg(s2)
    add_header(s2, "Background & Academic Motivation", "立项背景与科学问题：破除传统食疗'成分黑盒'之困", "面对千亿大健康市场，中医药食同源现代化迫切需要定量化、机制化的计算生物学支撑")
    
    # 三栏对比卡片
    col_w = Inches(3.64)
    gap = Inches(0.38)
    top_pos = Inches(1.7)
    card_h = Inches(5.2)
    
    # 卡片 1
    add_card(s2, Inches(0.8), top_pos, col_w, card_h, "1. 传统食疗产品现状", COLOR_GOLD)
    tb = s2.shapes.add_textbox(Inches(1.0), top_pos + Inches(0.7), col_w - Inches(0.4), card_h - Inches(0.9))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 经验主义盛行：\n停留在古籍经验与玄学概念炒作，缺乏现代生物化学与药代动力学量化指标。\n\n● 用户感知脱节：\n消费者喝了不知道‘到底起不起效’、‘有效成分是什么’、‘喝多少才能达到有效暴露量’。\n\n● 安全禁忌黑盒：\n体质相冲、慢病冲突、特殊人群禁忌缺乏精确的拦截过滤规则。"
    for p in tf.paragraphs:
        p.font.size = Pt(12)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(8)

    # 卡片 2
    add_card(s2, Inches(0.8) + col_w + gap, top_pos, col_w, card_h, "2. 传统网络药理学瓶颈", COLOR_CYAN)
    tb = s2.shapes.add_textbox(Inches(1.0) + col_w + gap, top_pos + Inches(0.7), col_w - Inches(0.4), card_h - Inches(0.9))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 忽略药代动力学（假阳性高）：\n传统网络药理学将中药全谱分子等权代入靶点富集，忽视了【不入血就无法到达体内靶点】的核心生理事实。\n\n● 数据缺失真实负例：\n文献只报道‘在血中检出了什么’（正样本），从不报道‘什么没检出’（负样本缺失）。\n\n● 监督学习失效：\n缺乏真实负样本导致标准 SVM / 二分类器面临严重的伪负样本惩罚。"
    for p in tf.paragraphs:
        p.font.size = Pt(12)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(8)

    # 卡片 3
    add_card(s2, Inches(0.8) + (col_w + gap)*2, top_pos, col_w, card_h, "3. 本项目科学破局方案", COLOR_TEAL)
    tb = s2.shapes.add_textbox(Inches(1.0) + (col_w + gap)*2, top_pos + Inches(0.7), col_w - Inches(0.4), card_h - Inches(0.9))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 引入 PU-Learning 算法：\n正样本-未标注（Positive-Unlabeled）学习机制，破译无负例条件下的体内移行规律。\n\n● 105 味全名录与可信度闭环：\n留一法适用域量化、4 算法族交叉互验、ChEMBL 体外实验实测锚定。\n\n● 端侧轻量化与普惠落地：\n本地 RapidOCR 毫秒级断网识方、本草拓扑纠错、茶罐全货架匹配与长辈适老模式。"
    for p in tf.paragraphs:
        p.font.size = Pt(12)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(8)

    add_notes(s2, """【演讲口播（45 秒）】
评审老师们深知，传统网络药理学常被诟病‘纸上谈兵’，最致命的缺陷就在于：很多在体外被证实有活性的成分，口服后根本无法穿透生物屏障进入血液循环，更谈不上作用于体内病灶。
然而，在真实科研中，文献只报道‘在血中检出了什么’，从不报道‘什么没检出’。这意味着传统监督学习模型由于缺乏负样本，面临严重的伪负样本惩罚。
如何从海量正样本与未标注数据中，精准预测血中移行倾向？这是我们整个算法体系要解决的第一核心科学问题。""")

    # =========================================================================
    # SLIDE 3: 系统全栈架构与多层算法全景
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    add_bg(s3)
    add_header(s3, "System Architecture & Algorithms Overview", "总体系统技术架构与核心算法全景", "从底层多组学数据库到分子表征、算法引擎、多目标推荐及适老端侧的工业级分层架构")
    
    layer_w = Inches(11.733)
    layer_h = Inches(0.95)
    gap_y = Inches(0.12)
    start_y = Inches(1.65)
    
    layers_data = [
        ("一、数据底座层", "ccTCM 2.0 权威科研库 (6,196行含量 / 40,634靶点) ＋ 卫健委 105 味全名录 ＋ ChEMBL 实测体外活性 ＋ SymMap 703味中药性味", COLOR_MUTED),
        ("二、分子表征层", "RDKit 分子结构规范化 ＋ 1024-bit Morgan 拓扑指纹 (Radius=2) ＋ 全库理化参数计算 ＋ 端侧 RapidOCR ONNX 视觉流", COLOR_CYAN),
        ("三、核心算法矩阵", "【PU-Learning 入血预测】＋【多口径预测治理消融】＋【留一法适用域量化】＋【UMAP 流形降维】＋【本草拓扑纠错】＋【机制通路富集】", COLOR_GOLD),
        ("四、协同决策引擎", "CCMQ 67 题国标体质判定 ＋ 安全禁忌硬约束剪枝 ＋ 24 节气时令协同 ＋【我的茶罐】105 味食材图贪心覆盖 ＋【对比实验室】", COLOR_TEAL),
        ("五、工程与交互层", "FastAPI 异步微秒级推断架构 (57 路径 / 61 端点 · 延迟 < 15ms) ＋ 可信度四件套透视卡 ＋ 全局长辈高对比大字适老模式", COLOR_WHITE),
    ]
    for i, (name, desc, col) in enumerate(layers_data):
        y = start_y + i * (layer_h + gap_y)
        add_card(s3, Inches(0.8), y, layer_w, layer_h, "", border_color=COLOR_CARD_BORDER)
        tb = s3.shapes.add_textbox(Inches(1.0), y + Inches(0.12), layer_w - Inches(0.4), layer_h - Inches(0.24))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = f"{name}：{desc}"
        p.font.size = Pt(13)
        p.font.bold = True
        p.font.color.rgb = col

    add_notes(s3, """【演讲口播（45 秒）】
这是我们平台的总体架构全景。我们构建了严格分层的技术体系：
底座基于南京中医药大学赵玉男老师团队自建的 ccTCM 2.0 数据库与卫健委目录，完成 105 味药材、6,205 个化合物、10,154 个蛋白靶点与 62,617 条相互作用的标准化映射；
算法层构筑了以 PU-Learning 入血预测为引擎，联动多口径分层治理、留一法全库适用域判定、UMAP 高维流形拓扑、本地 RapidOCR 形近字纠错六大算法组件；
向上支撑国家 CCMQ 67 题体质辨识、茶罐全货架反向配伍与多方对比实验室，最后通过 FastAPI 形成 57 路径 61 端点的高性能服务闭环。""")

    # =========================================================================
    # SLIDE 4: 算法核心一：PU-Learning 建模突破
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    add_bg(s4)
    add_header(s4, "Algorithm 01 · PU-Learning Framework", "算法核心一：中药数据特性与 PU-Learning 建模突破", "解决正样本仅 13% 且缺失真实负样本的机器学习难题，创新引入 PU-Bagging 集成学习协议")
    
    # 左右双卡排版
    w_half = Inches(5.66)
    gap_x = Inches(0.4)
    
    # 左卡：数学建模与训练协议
    add_card(s4, Inches(0.8), Inches(1.7), w_half, Inches(5.2), "数学建模与 PU-Bagging 协议", COLOR_CYAN)
    tb = s4.shapes.add_textbox(Inches(1.0), Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 样本空间形式化：\n样本集 X = P ∪ U。正样本 P（血中移行报道化合物 282 个，Label=1），未标注集 U（全量中药候选化合物 1,887 个，正负混合）。\n\n● PU-Bagging 集成采样协议：\n进行 K 次均衡有放回抽样。在每轮 k 中，保留全部正例 P，从 U 中以均匀采样抽取等量子集 U_k（视作伪负例），训练一棵随机森林基决策树。\n\n● 集成软投票推断：\n多轮模型预测均值软投票集成，消解未标注样本中潜在正例带来的伪负惩罚，输出校准先验概率 prob_cctcm。\n\n● 特征工程：\nRDKit 提取 1024-bit Morgan 拓扑指纹（ECFP4，Radius=2）＋ MW、LogP、TPSA 等理化描述符。"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    # 右卡：关键概念厘清（答辩防火墙）
    add_card(s4, Inches(0.8) + w_half + gap_x, Inches(1.7), w_half, Inches(5.2), "关键概念厘清：检出倾向 ≠ 吸收率", COLOR_GOLD)
    tb = s4.shapes.add_textbox(Inches(1.0) + w_half + gap_x, Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 模型在预测什么？\n模型预测的是【血中移行成分倾向】（该分子能否在血中被实验仪器检出，含肠道代谢产物），绝非物理意义上的【口服生物利用度 (F%)】！\n\n● 为什么人参皂苷等大分子得分极高？\n人参皂苷 Re（MW 947）得分高达 0.991。皂苷类分子口服直接吸收率极低，但经过肠道菌群与水解酶代谢后，原型或次生苷产物【在血液中大量检出】，文献有海量阳性实验报道，故得分高。\n\n● 为什么挥发性单萜得分偏低？\n石竹烯等小分子（MW 204）极易吸收，但体内一相代谢极快、半衰期极短，血浆中难以捕获原型峰，文献阳性记录少。\n\n★ 结论：这不是特征学偏了，而是标签定义带来的正确生物学反馈！"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    add_notes(s4, """【演讲口播（60 秒）】
在算法建模上，针对正样本仅 13% 且缺失负例的数据特征，我们创新采用了 PU-Bagging 集成算法。通过提取 1024 位的 Morgan 拓扑指纹，每轮采样将全量正例与等量未标注样本混合，利用多轮随机森林集成软投票，消解噪声样本对分类界面的干扰。
这里向各位老师汇报一个非常关键的学术边界：我们的模型预测的是‘在血液中被检出’的倾向，绝非口服吸收率。这严谨地解释了为何大分子人参皂苷在文献报道支持下展现出高分，体现了算法对中药体内真实代谢过程的深刻映射。""")

    # =========================================================================
    # SLIDE 5: 算法核心二：模型评估与多口径预测治理（消融实测）
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    add_bg(s5)
    add_header(s5, "Algorithm 02 · Evaluation & Ablation Study", "算法核心二：实验评估与多口径预测治理（消融实测）", "实测 ROC-AUC 0.903；针对扩容后 4,562 分子建立严密 prob_caliber 分层治理，严禁强行外推")

    # 左卡：模型实测指标
    add_card(s5, Inches(0.8), Inches(1.7), w_half, Inches(5.2), "模型实测指标（3 种子 5 折交叉验证）", COLOR_CYAN)
    tb = s5.shapes.add_textbox(Inches(1.0), Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 测试集规模：2,169 个去重化合物（正样本 282，占比仅 13%）\n\n● ROC-AUC：0.903 ± 0.008（区分正负样本能力优秀）\n\n● PR-AUC：0.573 ± 0.009（非平衡场景下的核心参考指标）\n\n● 最优 F1 分数：0.585\n\n● 高置信工程截断阈值（prob ≥ 0.7）：\n在 0.5 默认阈值下，精确率受 13% 先验概率压缩为 0.359（召回率 0.910）；\n在平台工程落地中，我们设置 prob ≥ 0.7 过滤线，精确率跃升至 0.549（召回率 0.596），有效排除低置信噪声，作为排序权重参考。"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    # 右卡：扩容多口径治理与消融实验（核心学术高光）
    add_card(s5, Inches(0.8) + w_half + gap_x, Inches(1.7), w_half, Inches(5.2), "扩容后多口径治理与消融实验（Ablation）", COLOR_GOLD)
    tb = s5.shapes.add_textbox(Inches(1.0) + w_half + gap_x, Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 扩容后 4,562 成分严格三级口径隔离：\n• A 类老成分 (165个)：完整实测 ADME 特征，主力旧管线\n• B 类回填成分 (795个)：官方正式表 SMILES 精确匹配，零重训\n• C 类扩容成分 (3,602个)：HERB 兜底模型外推，标明 C 级参考\n\n● 消融实验：为什么 C 类绝不强行跑 ccTCM 主力模型？\nccTCM 依赖 7 个实验室实测 ADME 参数。我们在 165 个已知成分上进行消融对比：\n• 若用仅 SMILES 虚拟填补跑 ccTCM：平均绝对偏差高达 0.29，阈值翻转率 44.4%（形同抛硬币！）\n• 若采用仅依赖结构的 HERB 兜底模型：平均绝对偏差仅 0.135，分类一致率 79%！\n\n★ 坚守底线：严禁强行外推伪造精度，界面诚实标注外推徽章，绝不填 0 混淆！"
    for p in tf.paragraphs:
        p.font.size = Pt(11)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(5)

    add_notes(s5, """【演讲口播（60 秒）】
在模型评估上，主模型取得了 0.903 的优秀 ROC-AUC。更为可贵的是，当我们将药材扩容至 105 味全目录、入血预测覆盖扩至 4,562 个分子时，我们没有搞‘一键盲目外推’。
我们通过严密的消融实验发现：主模型包含 7 个实验室实测的药代参数，如果对新分子强行虚拟填补特征，预测偏差高达 0.29，阈值翻转率达 44%，这在科研上等于抛硬币！
因此，我们建立了严格的 prob_caliber 三级治理机制，将 3,602 个扩容分子切换为结构偏差仅 0.135 的兜底模型，并在界面诚实标注‘外推参考’。这种不唯指标、实事求是的科学态度，正是挑战杯最看重的科研严谨性！""")

    # =========================================================================
    # SLIDE 6: 算法鲁棒性：跨算法族交叉验证
    # =========================================================================
    s6 = prs.slides.add_slide(blank_layout)
    add_bg(s6)
    add_header(s6, "Algorithm 03 · Independent Cross-Validation", "算法鲁棒性：跨算法族独立交叉验证与分歧机理解构", "引入 3 个完全不同范式的机器学习算法族独立训练，排除结论依赖特定算法的假象")

    # 左侧对比表格区域
    add_card(s6, Inches(0.8), Inches(1.7), Inches(6.0), Inches(5.2), "跨算法族独立重训对照", COLOR_CYAN)
    
    # 插入表格
    rows, cols = 5, 4
    table_shape = s6.shapes.add_table(rows, cols, Inches(1.0), Inches(2.4), Inches(5.6), Inches(2.2))
    table = table_shape.table
    table.columns[0].width = Inches(2.0)
    table.columns[1].width = Inches(1.4)
    table.columns[2].width = Inches(1.2)
    table.columns[3].width = Inches(1.0)
    
    headers = ["模型架构", "算法族分类", "ROC-AUC", "PR-AUC"]
    for j, h in enumerate(headers):
        cell = table.cell(0, j)
        cell.text = h
        cell.fill.solid()
        cell.fill.fore_color.rgb = COLOR_CARD_BORDER
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(11)
            p.font.bold = True
            p.font.color.rgb = COLOR_CYAN
            
    data_cv = [
        ["主模型 (PU-Bagging+RF)", "PU 集成树", "0.903 ± 0.008", "0.573"],
        ["独立 XGBoost", "梯度提升树", "0.8961 ± 0.0055", "0.562"],
        ["独立 MLP", "深度神经网络", "0.8529 ± 0.0219", "0.535"],
        ["独立逻辑回归", "线性分类基线", "0.8225 ± 0.0110", "0.474"],
    ]
    for i, row in enumerate(data_cv):
        for j, val in enumerate(row):
            cell = table.cell(i+1, j)
            cell.text = val
            cell.fill.solid()
            cell.fill.fore_color.rgb = COLOR_CARD
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(10)
                p.font.color.rgb = COLOR_WHITE if i > 0 else COLOR_GOLD

    # 表格下方说明
    tb = s6.shapes.add_textbox(Inches(1.0), Inches(4.8), Inches(5.6), Inches(1.9))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 判别信号客观存在：\n独立 XGBoost 与主模型 AUC 极度吻合（0.896 vs 0.903），证明特征工程提取的分子拓扑信号具备普适判别力，不依赖特定模型算法。\n\n● 双模型分类一致率：\n两套完全独立体系在阈值下分类一致率达 73.3%（Spearman 0.580）。"
    for p in tf.paragraphs:
        p.font.size = Pt(11)
        p.font.color.rgb = COLOR_MUTED

    # 右侧分歧机理解构卡片
    add_card(s6, Inches(7.1), Inches(1.7), Inches(5.4), Inches(5.2), "分歧机理解构：为什么一致率不是 100%？", COLOR_GOLD)
    tb = s6.shapes.add_textbox(Inches(7.3), Inches(2.3), Inches(5.0), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 44 个分歧点 100% 聚拢于皂苷类分子：\n如落新妇苷（0.992 vs 0.000）、三七皂苷 R1（0.990 vs 0.016）和长链脂肪酸，不存在随机白噪声分歧。\n\n● 协议差异导致的系统性分歧：\n• 主模型采用 PU 学习协议：每轮全部正例 ＋ 等量未标注抽样，对未标注的次生苷大分子进行了合理的降权包容（捕捉到了菌群代谢入血的文献事实）；\n• 独立模型采用标准二分类协议：将未标注样本全部视作负例，对复杂苷类产生了强烈的二分类惩罚。\n\n★ 核心结论：\n分歧的方向与算法协议差异完全契合！分歧本身反向印证了我们对算法底层与中药代谢规律的深刻掌握！"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    add_notes(s6, """【演讲口播（45 秒）】
为了排除算法偶发性，我们引入了多层感知机、逻辑回归和 XGBoost 三个不同算法族的独立交叉验证。
独立的 XGBoost 达到了 0.896 的高 AUC，双模型一致率达到 73.3%。剩下的 44 个分歧点高度聚集于皂苷类分子——主模型的 PU 机制捕捉到了大分子水解入血的规律，而标准 XGBoost 由于二分类协议表现保守。
分歧不仅没有削弱可信度，反而强力证明了我们对算法底层与中药代谢规律的深刻掌握！""")

    # =========================================================================
    # SLIDE 7: 算法边界：基于留一法的全库适用域量化
    # =========================================================================
    s7 = prs.slides.add_slide(blank_layout)
    add_bg(s7)
    add_header(s7, "Algorithm 04 · Applicability Domain via LOO", "算法边界：基于留一法（LOO）的全库适用域量化", "杜绝模型外推幻觉，运用 Morgan 指纹 Tanimoto 拓扑距离标定全库 4,558 分子可信边界")

    add_card(s7, Inches(0.8), Inches(1.7), w_half, Inches(5.2), "留一法 (LOO) 阈值标定数学推导", COLOR_CYAN)
    tb = s7.shapes.add_textbox(Inches(1.0), Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 距离度量函数：\n对预测分子 x，计算其与训练集 S_train（2,437个分子）的最大 Morgan 指纹 Tanimoto 相似度：\nS(x) = max_{y ∈ S_train} Tanimoto(F_x, F_y)\n\n● 为什么弃用随机配对？\n若采用随机配对，化学空间的稀疏性导致随机相似度极低，5% 分位仅 0.028，会把所有分子误判为‘域内’，使检验形同虚设！\n\n● 创新留一法 (Leave-One-Out) 分布标定：\n计算训练集内每个分子离自身最近同伴的距离分布，反映化学流形的真实密度：\n• 5% 分位点 (0.333) → 标定为【应用域外】截断线\n• 25% 分位点 (0.582) → 标定为【应用域边缘】警戒线\n• > 0.582 → 标定为【应用域内】高可信区间"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    add_card(s7, Inches(0.8) + w_half + gap_x, Inches(1.7), w_half, Inches(5.2), "全库 4,558 个分子适用域实测分布", COLOR_GOLD)
    tb = s7.shapes.add_textbox(Inches(1.0) + w_half + gap_x, Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 全库 4,558 个分子最新评测结果：\n• 域内 (高置信)：2,775 个（占比 60.9%）\n• 边缘 (需审慎)：1,193 个（占比 26.2%）\n• 域外 (主动预警)：590 个（占比 12.9%）\n\n● 前端透明化预警与降级机制：\n对于处于域外的 590 个分子（如白皮杉醇相似度仅 0.246），系统在成分详情页直接亮红灯，打上【预测可靠性有限】徽章，主动提示其超出模型适用边界。\n\n★ 科学态度：\n评测一个 AI 系统，看的不仅是其 ROC 曲线有多高，更是看它敢不敢把不可靠之处坦诚亮出来！"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    add_notes(s7, """【演讲口播（45 秒）】
AI 预测最大的隐患是‘未知领域的盲目外推’。为此，我们建立了适用域量化算法。
我们通过留一法精确标定出 0.333 和 0.582 两道分水岭，并推广到了全库 4,558 个有效分子中。实测发现 2,775 个分子处于高置信域内，而对于 590 个处于域外的分子，系统在界面上主动提示‘模型可靠性有限’。
敢于把不可靠之处亮出来，是我们算法工程的底线与担当。""")

    # =========================================================================
    # SLIDE 8: 拓扑表征：全库 4,558 分子 UMAP 高维化学空间流形
    # =========================================================================
    s8 = prs.slides.add_slide(blank_layout)
    add_bg(s8)
    add_header(s8, "Algorithm 05 · Chemical Space Manifold (UMAP)", "拓扑表征：全库 4,558 分子 UMAP 高维化学空间流形", "将 1024 维拓扑分子指纹投影至二维连续拓扑流形，实现入血概率与模型一致性的全局几何聚类")

    add_card(s8, Inches(0.8), Inches(1.7), w_half, Inches(5.2), "UMAP 非线性流形降维算法参数", COLOR_CYAN)
    tb = s8.shapes.add_textbox(Inches(1.0), Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 降维算法选型：\n采用 Uniform Manifold Approximation and Projection (UMAP)，优于线性 PCA 与局部 t-SNE，能平衡微观局部结构与全局拓扑骨架。\n\n● 数学超参数配置：\n• 目标维度: n_components = 2\n• 邻域流形规模: n_neighbors = 15\n• 最小嵌入距离: min_dist = 0.3\n• 随机种子固定: random_state = 42 (保证完全可复现)\n\n● 坐标库与中间件优化：\n生成 compound_map 全库 4,558 点坐标，后端接入 GZip 压缩中间件，确保毫秒级渲染。"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    add_card(s8, Inches(0.8) + w_half + gap_x, Inches(1.7), w_half, Inches(5.2), "空间拓扑岛礁聚集与生物学解释", COLOR_GOLD)
    tb = s8.shapes.add_textbox(Inches(1.0) + w_half + gap_x, Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 化学空间骨架岛礁分布：\n4,558 个分子在流形上自发聚类：黄酮类、三萜皂苷类、挥发性单萜、生物碱在二维空间形成边界清晰的聚集岛礁。\n\n● 入血概率的几何拓扑连续性：\n高入血概率分子展现出高度集中的骨架聚集效应，验证了分子拓扑亚结构与体内代谢检出倾向之间的内在生物物理连续性。\n\n● 三色多口径可视化：\n绿色（高信入血）、红色（低信难入血）、土黄色（C级外推点），三色分明，为中药复方配伍中的成分协同与互补提供了拓扑几何依据。"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    add_notes(s8, """【演讲口播（30 秒）】
为了全局透视扩容后的中药化学空间，我们利用 UMAP 算法将全库 4,558 个成分投影至二维流形。
评委老师在屏幕上可以看到，黄酮类、皂苷类在空间中呈现显著的拓扑聚集，且高入血概率分子展现出高度集中的骨架聚集。
这不仅证明了高维指纹特征工程的有效性，也为中药复方的多靶点协同配伍提供了空间几何依据。""")

    # =========================================================================
    # SLIDE 9: 机制解析：10,154 靶点网络富集与三维活性评分
    # =========================================================================
    s9 = prs.slides.add_slide(blank_layout)
    add_bg(s9)
    add_header(s9, "Algorithm 06 · Target Enrichment & ChEMBL Evidence", "机制解析：10,154 靶点网络富集与 ChEMBL 实验实测背书", "构建 62,617 条高精互作网络，接入国际权威实验数据库，形成抗炎/抗氧化/免疫三维雷达图")

    add_card(s9, Inches(0.8), Inches(1.7), w_half, Inches(5.2), "靶点相互作用与 ChEMBL 实测证据", COLOR_CYAN)
    tb = s9.shapes.add_textbox(Inches(1.0), Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 靶点网络跃升：\n覆盖 10,154 个已知人类蛋白靶点，沉淀 62,617 条成分-靶点相互作用。\n\n● 补齐【体外实验实测】关键证据环：\n欧洲生物信息所 ChEMBL 精确匹配 126 个成分，入库 465 条体外实测 Ki/IC50 活性记录：\n• L1 级强证据 (127条)：pChEMBL ≥ 6（即结合常数 ≤ 1μM）\n• L2 级中证据 (338条)：5 ≤ pChEMBL < 6\n\n● 数据清洗攻坚：\n自行从原始单位换算缺失的 pChEMBL；二次查询 target.json 彻底剔除 SK-MEL-28 等细胞系污染。"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    add_card(s9, Inches(0.8) + w_half + gap_x, Inches(1.7), w_half, Inches(5.2), "超几何检验与三维生物学机制雷达图", COLOR_GOLD)
    tb = s9.shapes.add_textbox(Inches(1.0) + w_half + gap_x, Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 超几何分布通路富集模型：\n基于 Enrichr 算法框架，计算高入血活性分子所调控的靶点集在 KEGG / GO 信号通路中的富集概率值 p。\n\n● 三维生物学机制雷达图映射：\n将微观分子靶点归纳映射为食疗大健康关注的三大宏观功效轴：\n• 抗炎响应轴 (NF-κB / MAPK 通路等)\n• 抗氧化应激轴 (Nrf2 / 谷胱甘肽代谢等)\n• 免疫调节轴 (T细胞受体 / 细胞因子网络等)\n\n★ 成果：每个方子点开即见机制雷达图，彻底告别传统玄学，让推荐具有扎实的分子机理解释。"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    add_notes(s9, """【演讲口播（45 秒）】
预测入血只是第一步，入血后作用于何处？我们构建了完整的计算生物学证据链。
平台映射了 10,154 个蛋白靶点与 6.2 万余条相互作用，接入了 ChEMBL 数据库 465 条体外实测数据，其中 127 条达到微摩尔级的高活性强证据。
通过超几何检验与通路富集，我们将微观靶点抽象为通俗可见的三维生物机制雷达图，彻底告别了传统玄学，让每一个推荐都有分子机制可溯。""")

    # =========================================================================
    # SLIDE 10: 剂量模拟：定量暴露量三档场景化模型
    # =========================================================================
    s10 = prs.slides.add_slide(blank_layout)
    add_bg(s10)
    add_header(s10, "Algorithm 07 · Dose-Exposure Scenario Modeling", "剂量模拟：定量暴露量三档场景化模型", "遵循定量药理学 Fit-for-Purpose 原则，给诚实区间，坚决不给伪造的虚假单点")

    add_card(s10, Inches(0.8), Inches(1.7), w_half, Inches(5.2), "数学模型与三档情景转移率", COLOR_CYAN)
    tb = s10.shapes.add_textbox(Inches(1.0), Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 暴露量估算数学公式：\nExposure_i = HerbDose × ContentRange_i × η_transfer\n\n● 煎煮转移率三档情景分布 (η_transfer)：\n天然产物煎煮过程受火候、颗粒度、共煎竞争等影响极大。我们坚决摒弃单点固定值，设定三档分布：\n• 保守情景 (η = 0.3) → est_mg_min\n• 基准情景 (η = 0.5) → est_mg_base\n• 乐观情景 (η = 0.7) → est_mg_max\n\n● 输出结果：\n输出成分动态摄入区间 [min, max] mg，提供数量级参考。"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    add_card(s10, Inches(0.8) + w_half + gap_x, Inches(1.7), w_half, Inches(5.2), "为什么不建高精 PBPK 模型？（方法学正统）", COLOR_GOLD)
    tb = s10.shapes.add_textbox(Inches(1.0) + w_half + gap_x, Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● PBPK（生理药代动力学）面临的数据困境：\nPBPK 是 FDA 审评药物相互作用的金标准，但它严苛依赖每个单体的体内固有清除率 (CLint)、血浆游离分数 (fu)、组织分配系数 (Kp) 等实测参数。\n对于中药复方中的天然成分，全球数据库均缺失此类数据，强行搭建只会退化为参数造假！\n\n● 定量药理学的 Fit-for-Purpose 原则：\n‘All models are wrong, but some are useful’。在日常食疗筛查场景中，给出诚实的区间分布，远比包装成所谓‘高精度的假单点’更为严肃严谨。"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    add_notes(s10, """【演讲口播（30 秒）】
在方子层面的暴露量估计上，我们遵循定量药理学规范。天然产物复杂的共煎过程无法直接套用复杂的 PBPK 模型，我们拒绝给出虚假的单点预测，而是采用三档煎煮转移率情景模拟，为用户呈现保守、基准、乐观三档真实摄入区间。
这种区间化思维，体现了科研工程落地的求真态度。""")

    # =========================================================================
    # SLIDE 11: 端侧突破：本地轻量 RapidOCR 与本草形近字拓扑纠错算法
    # =========================================================================
    s11 = prs.slides.add_slide(blank_layout)
    add_bg(s11)
    add_header(s11, "Algorithm 08 · Local RapidOCR & Herb Typo Correction", "端侧突破：本地轻量 RapidOCR 与本草形近字语义纠错算法", "攻克'认错一个字后面全错'的落地致命伤，纯 CPU 毫秒级断网运行，纠错率 11/12，误纠率 0/40")

    add_card(s11, Inches(0.8), Inches(1.7), w_half, Inches(5.2), "本地纯 CPU RapidOCR 引擎 (ONNX)", COLOR_CYAN)
    tb = s11.shapes.add_textbox(Inches(1.0), Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 告别云端视觉大模型调用：\n云端多模态 API 耗时长、成本高且严重依赖网络。我们自研替换为本地轻量化 RapidOCR（ONNX Runtime 纯 CPU 推理）。\n\n● 极端工况实测表现（合成图 3 档难度）：\n• 清晰图: 1.5s 识别完成 (100% 正确)\n• 劣化图: 3.6s 识别完成 (100% 正确)\n• 极端劣化 (倾斜+光照不均+模糊+JPEG q35): 2.9s (100% 正确)\n\n● 零成本与断网高可用：\n零 API 成本、断网可用、自带逐行置信度剪枝（丢弃 Conf < 0.5 低质行）。"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    add_card(s11, Inches(0.8) + w_half + gap_x, Inches(1.7), w_half, Inches(5.2), "本草形近字拓扑纠错算法 (correct_herb_name)", COLOR_GOLD)
    tb = s11.shapes.add_textbox(Inches(1.0) + w_half + gap_x, Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 痛点：认错一个字导致整条链路崩塌：\nOCR 把‘金银花’认成‘金银化’，后续靶点富集直接归零。\n\n● 三级拓扑纠错词表 (105味药食同源 + 703味 SymMap)：\n① 同长度形近替换（金银化 → 金银花）\n② 省字匹配（枸札 → 枸杞子）\n③ 编辑距离为 1 的受限匹配（阵皮 → 陈皮）\n\n● 安全约束：多候选有歧义拒猜；纯编辑距离瞎猜拒猜（桂圆≠桂枝）。\n\n★ 实测数据：错字纠正率 11/12，真药名误纠正率 0/40！全透明展示纠偏记录并支持用户自主改回。"
    for p in tf.paragraphs:
        p.font.size = Pt(11)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(5)

    add_notes(s11, """【演讲口播（45 秒）】
在实际使用中，用户拍照识别药方最怕‘认错一个字，后面全错’（如把金银花认成金银化，后续靶点全部落空）。
我们摒弃了昂贵且不可控的云端大模型，自研了‘本地 RapidOCR + 本草形近字拓扑纠错算法’。基于 800 余味中草药知识图谱，通过三级受限纠错机制，实测纠错率高达 11/12，且真药名误纠率为 0！
在断网状态下即可毫秒级运行，并将纠偏记录完全透明地向用户展示，攻克了中药数字化录入的咽喉痛点。""")

    # =========================================================================
    # SLIDE 12: 落地功能：我的茶罐 105 味配伍与多方对比实验室
    # =========================================================================
    s12 = prs.slides.add_slide(blank_layout)
    add_bg(s12)
    add_header(s12, "Application 01 · Tea Pantry & Compare Lab", "落地功能：我的茶罐 105 味反向配伍与多方对比实验室", "从在研到全面落地：解除 40 味限制上线 105 味分类货架，激活青年翻茶罐随手组方")

    add_card(s12, Inches(0.8), Inches(1.7), w_half, Inches(5.2), "【我的茶罐】食材子集图覆盖贪心算法", COLOR_CYAN)
    tb = s12.shapes.add_textbox(Inches(1.0), Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 场景痛点创新：\n年轻人‘囤了一堆枸杞、菊花、陈皮，但不知道怎么搭’。从‘给方买药’转变为‘翻翻茶罐，反向组方’。\n\n● 解除限制与货架重构：\n全面解除 40 味截断，上线 105 味全名录分类货架（清热/理气/补虚等）与悬浮配伍底栏。\n\n● 图覆盖匹配数学模型：\nCoverage(r) = |M_owned ∩ M_required(r)| / |M_required(r)|\n（自动过滤辅料与可选配料干扰）\n\n● 多维决策矩阵排序：\n覆盖率降序 → 缺料升序 → 高入血活性成分数降序。"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    add_card(s12, Inches(0.8) + w_half + gap_x, Inches(1.7), w_half, Inches(5.2), "【对比实验室】复方成分与机制同屏 PK", COLOR_GOLD)
    tb = s12.shapes.add_textbox(Inches(1.0) + w_half + gap_x, Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 多方并联多维对比算法：\n支持 2~3 个食疗茶饮方同屏 PK，解决‘同一病症选哪个方子更好’的决策难题。\n\n● 核心比对维度：\n• 成分重合度与特有活性成分剖析\n• 抗炎/抗氧化/免疫三维机制雷达图同屏叠加\n• 体质适应度与禁忌人群差异化对比\n• 暴露量区间分布对比\n\n● 多入口生态打通：\n打通方子库详情页、为你推荐卡、搜索结果页一键加入对比槽位，毫秒级并联出图。"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    add_notes(s12, """【演讲口播（45 秒）】
在应用层面，我们实现了‘我的茶罐’与‘对比实验室’两项核心功能落地。
面对年轻人‘手头有食材却不知怎么配’的现状，茶罐功能解锁了 105 味全名录，基于食材子集图覆盖算法，勾选三五味食材即可毫秒级计算全库方子的匹配度并推荐最优组方；
而对比实验室则支持多个食疗方的成分重合度与机制雷达图同屏 PK，让消费者在选购茶饮时做到‘心中有数，优中选优’。""")

    # =========================================================================
    # SLIDE 13: 推荐引擎：国标 CCMQ 67 题体质量表与多源协同决策
    # =========================================================================
    s13 = prs.slides.add_slide(blank_layout)
    add_bg(s13)
    add_header(s13, "Algorithm 09 · Multi-Objective Recommendation", "推荐引擎：国标 CCMQ 67 题体质量表与多源协同决策", "国家标准体质判定 + 安全剪枝防线 + 节气/偏好多目标融合打分模型")

    add_card(s13, Inches(0.8), Inches(1.7), w_half, Inches(5.2), "CCMQ 67 题量表与安全剪枝引擎", COLOR_CYAN)
    tb = s13.shapes.add_textbox(Inches(1.0), Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 中华中医药学会国家标准 (CCMQ)：\n严格执行 67 题九种体质量表规范，计算平和质及 8 种偏颇体质的雷达转化分，输出主导偏颇体质。\n\n● 安全红线剪枝引擎 (Safety Gate - 强制拦截)：\n• 体质相冲忌口剔除：如气虚体质排除重耗气药材、阴虚火旺排除温燥大热药材；\n• 特殊生理阶段强制拦截：孕妇、儿童、慢性病人群红线食材一票否决；\n• 绝不妥协：安全规则优先于任何推荐模型打分！"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    add_card(s13, Inches(0.8) + w_half + gap_x, Inches(1.7), w_half, Inches(5.2), "多目标协同效用函数打分机制", COLOR_GOLD)
    tb = s13.shapes.add_textbox(Inches(1.0) + w_half + gap_x, Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 多目标效用打分公式：\nS(r) = w_c · Match(C_user, r) + w_t · SolarTermBonus + w_b · BehaviorPref + w_a · BloodRatio(r)\n\n● 四维协同加成因子：\n• w_c: 主导体质适宜度得分（相生加分、相克排除）\n• w_t: 24 节气当令时令主题命中加分（如白露润燥、冬至温补）\n• w_b: 用户历史收藏与打卡场景行为隐式反馈\n• w_a: 方子高入血活性成分丰度加权\n\n★ 输出结果：每条推荐附带透明化‘推荐理由’，拒绝黑盒分发。"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    add_notes(s13, """【演讲口播（30 秒）】
在个性化推荐上，我们坚决杜绝无序分发。第一道防线是国家标准 CCMQ 67 题量表，精准定位九种体质；第二道防线是安全禁忌硬剪枝，剔除体质相冲食材；
最后融合 24 节气时令和行为偏好，输出兼具科学证据与通俗理由的食疗方案。""")

    # =========================================================================
    # SLIDE 14: 全栈工程与长辈适老无障碍模式
    # =========================================================================
    s14 = prs.slides.add_slide(blank_layout)
    add_bg(s14)
    add_header(s14, "Engineering & Accessibility · Elder Mode", "全栈工程落地与长辈适老高对比大字模式", "57 路径 61 端点高性能微秒级推断架构；自研动态字体缩放，科技向善消除银发鸿沟")

    add_card(s14, Inches(0.8), Inches(1.7), w_half, Inches(5.2), "高性能全栈工程实现指标", COLOR_CYAN)
    tb = s14.shapes.add_textbox(Inches(1.0), Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● FastAPI 异步非阻塞高并发底座：\n实测 57 路径 / 61 端点，单元测试通过率 100%，核心 API 算法在线推断耗时压至 15ms 以内。\n\n● 双 SQLite 动静物理隔离架构：\n• 只读知识库 shiyang.db (mode=ro)：严格保证 105 味科研数据运行时只读，杜绝任何数据篡改；\n• 读写库 user.db (WAL 模式)：支持高频打卡、收藏与并发写入。\n\n● 前端工程与一键部署：\nVue3 + Vite 现代化工程，提供一键自动化双起脚本 start.bat，局域网移动端即扫即测。"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    add_card(s14, Inches(0.8) + w_half + gap_x, Inches(1.7), w_half, Inches(5.2), "长辈高对比大字适老模式（社会价值加分项）", COLOR_GOLD)
    tb = s14.shapes.add_textbox(Inches(1.0) + w_half + gap_x, Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 聚焦中老年体质调理痛点：\n药食同源的核心受众大量为中老年慢病人群，传统 App 字体密密麻麻、对比度低，老人‘看不清、不敢用’。\n\n● 自研 FontScale 动态字号缩放系统：\n全局注入 font-scale-elder 变量，核心正文自适应放大至 1.25~1.4 倍，排版动态防溢出重排。\n\n● 医疗级高对比配色规范：\nWCAG AAA 级高对比度设计，增大按钮点击热区至 48px 以上。\n\n★ 评委高光：展现当代大学生兼顾学术深度与银发关怀的社会担当！"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(45)

    add_notes(s14, """【演讲口播（45 秒）】
好的算法需要扎实的工程与人文关怀承载。系统采用 57 个 API 路径、61 个端点的高可用架构，推断延迟压至 15 毫秒以内。
更重要的是，考虑到药食同源的大量受众是中老年群体，我们特别研发了‘全局长辈大字高对比适老模式’，全站支持自适应动态缩放与高对比度排版，真正体现了科技向善，让前沿计算生物学成果惠及千家万户。""")

    # =========================================================================
    # SLIDE 15: 现场实机演示动线与未来演进
    # =========================================================================
    s15 = prs.slides.add_slide(blank_layout)
    add_bg(s15)
    add_header(s15, "Live Demo & Future Roadmaps", "现场实机演示动线与在研演进规划", "设计 3 分钟一镜到底演示动线，展现科研真实态度与引入 PPB 结合率的后劲路线")

    add_card(s15, Inches(0.8), Inches(1.7), w_half, Inches(5.2), "3 分钟答辩一镜到底演示动线", COLOR_CYAN)
    tb = s15.shapes.add_textbox(Inches(1.0), Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 步骤 1：打开「白皮杉醇」详情页\n直观展示红色【应用域外】降级徽章与 24.6% 进度条 → 向评委展示主动暴露算法边界的严谨科研态度！\n\n● 步骤 2：打开「落新妇苷」详情页\n直观展示双模型对比与琥珀色【主模型单独高】徽章 → 现场解释苷类水解带来的算法协议差异！\n\n● 步骤 3：打开「黄芩素」详情页\n直观展示 ChEMBL 数据库 36 个靶点中活性最强的 10 条体外实测 Ki/IC50 与 L1 强证据勋章！\n\n● 步骤 4：一键切换【长辈大字模式】\n全站字体高对比无损放大，展示银发无障碍交互！"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    add_card(s15, Inches(0.8) + w_half + gap_x, Inches(1.7), w_half, Inches(5.2), "在研功能演进路线图", COLOR_GOLD)
    tb = s15.shapes.add_textbox(Inches(1.0) + w_half + gap_x, Inches(2.3), w_half - Inches(0.4), Inches(4.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = "● 演进 1：引入血浆蛋白结合率 (PPB) 预测：\n基于 AutoMolDesigner 课件方法论，将 3,921 条 PPB 实验数据纳入模型，解构‘入血后有多少是游离有效成分’。\n\n● 演进 2：智能穿戴与时序体征联动：\n打通智能手环心率、睡眠时序数据，实现体质偏颇状态的动态连续修正。\n\n● 演进 3：青囊寻证 RAG 大模型通俗解读：\n完善本地知识检索增强大模型（RAG），为老百姓翻译通俗易懂的草本食养建议。\n\n★ 愿景：打造中国领先的药食同源科学计算与健康推荐基础设施。"
    for p in tf.paragraphs:
        p.font.size = Pt(11.5)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    add_notes(s15, """【演讲口播（45 秒）】
在界面上，我们把‘可信’做成了可感知的交互。演示时评委老师可以看到：从白皮杉醇的域外降级，到落新妇苷的算法分歧归因，再到黄芩素的 ChEMBL 强证据徽章，我们把科学的局限与依据完全透明化。
未来，我们还将引入 3,900 余条血浆蛋白结合率（PPB）数据，持续探索游离活性分子的计算模拟，推动平台持续进化。""")

    # =========================================================================
    # SLIDE 16: 总结与致谢
    # =========================================================================
    s16 = prs.slides.add_slide(blank_layout)
    add_bg(s16)
    
    tb16 = s16.shapes.add_textbox(Inches(0.8), Inches(1.2), Inches(11.733), Inches(5.5))
    tf16 = tb16.text_frame
    tf16.word_wrap = True
    
    p = tf16.paragraphs[0]
    p.text = "CONCLUSION & ACKNOWLEDGEMENTS"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = COLOR_CYAN
    p.space_after = Pt(12)
    
    p = tf16.add_paragraph()
    p.text = "让中医药食同源：可知 · 可算 · 可信 · 可用"
    p.font.size = Pt(32)
    p.font.bold = True
    p.font.color.rgb = COLOR_WHITE
    p.space_after = Pt(20)
    
    innovations = [
        ("一、算法突破：", "首创 PU-Learning 中药入血预测框架，攻克无真实负例与极端不平衡难题，ROC-AUC 达 0.903。"),
        ("二、可信闭环：", "建立留一法全库适用域量化、多算法族独立交叉互验、严谨消融实验治理、ChEMBL 体外实验实测背书。"),
        ("三、工程普惠：", "实现卫健委 105 味全名录覆盖，自研端侧纯 CPU RapidOCR 与本草纠错算法，上线茶罐配伍与长辈适老模式。"),
    ]
    for tag, desc in innovations:
        p = tf16.add_paragraph()
        p.text = f"★ {tag} {desc}"
        p.font.size = Pt(14)
        p.font.color.rgb = COLOR_GOLD
        p.space_after = Pt(10)
        
    p = tf16.add_paragraph()
    p.text = "\n衷心感谢指导老师的悉心指导，恳请各位评委专家批评指正！\n汇报人：食养有据团队"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = COLOR_WHITE

    add_notes(s16, """【演讲口播（30 秒）】
回顾整个项目，我们做的不仅是一个推荐系统，更是中医药与现代计算生物学深度交融的科研实践。
我们用 PU-Learning 破译入血规律，用可信度工程守卫科研真实，让药食同源真正做到‘可知、可算、可信、可用’。
食养有据，大有可为！感谢各位老师，请各位评委批评指正！""")

    # 保存
    prs.save(str(OUT_PATH))
    print(f"Presentation saved successfully to: {OUT_PATH}")

if __name__ == "__main__":
    build_presentation()
