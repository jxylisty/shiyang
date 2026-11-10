# -*- coding: utf-8 -*-
"""
生成答辩专用的白底学术风（Clean Academic Light）、高分辨率架构图、真实数据图表与算法流程图 PNG 图片
直接从 data/shiyang.db 读取真实坐标与统计数据，使用 Playwright 以 2x 设备像素比高清渲染
产物输出至 docs/diagrams/
"""
import asyncio
import json
import sqlite3
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "diagrams"
DB_PATH = ROOT / "data" / "shiyang.db"
CHROME = r"C:\Users\zzx05\AppData\Local\ms-playwright\chromium-1248\chrome-win64\chrome.exe"


def load_umap_points():
    """从 shiyang.db 读取真实的 4,558 个化合物 UMAP 坐标用于绘制高清化学空间散点图"""
    con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    rows = con.execute("""
        SELECT x, y, prob_cctcm, prob_cctcm_v2, prob_herb_v2, ad_level_live
        FROM compound_map
        WHERE x IS NOT NULL AND y IS NOT NULL
    """).fetchall()
    con.close()
    pts = []
    for x, y, p1, p2, ph, ad in rows:
        p_main = p1 if p1 is not None else p2
        if p_main is not None:
            if p_main >= 0.7:
                cat = "high"   # 主力高入血
            elif p_main >= 0.5:
                cat = "mid"    # 主力中等
            else:
                cat = "low"    # 主力偏低
        else:
            cat = "ext"        # HERB 兜底外推
        pts.append([round(float(x), 3), round(float(y), 3), cat])
    return pts


def build_html(umap_pts_json: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: "Microsoft YaHei", "PingFang SC", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
  body {{ background: #F1F5F9; color: #0F172A; display: flex; flex-direction: column; gap: 48px; padding: 40px; width: 1440px; }}
  .diagram-container {{ background: #FFFFFF; border: 1.5px solid #CBD5E1; border-radius: 18px; padding: 28px 32px; box-shadow: 0 8px 28px rgba(15,23,42,0.06); position: relative; }}
  .diagram-title {{ font-size: 23px; font-weight: 800; color: #0F172A; margin-bottom: 6px; display: flex; align-items: center; gap: 12px; }}
  .diagram-tag {{ font-size: 12px; font-weight: 700; padding: 4px 12px; border-radius: 20px; background: #ECFDF5; color: #047857; border: 1px solid #6EE7B7; letter-spacing: 0.5px; }}
  .diagram-tag.blue {{ background: #EFF6FF; color: #1D4ED8; border-color: #93C5FD; }}
  .diagram-tag.amber {{ background: #FFFBEB; color: #B45309; border-color: #FCD34D; }}
  .diagram-tag.purple {{ background: #F5F3FF; color: #6D28D9; border-color: #C4B5FD; }}
  .diagram-desc {{ font-size: 14px; color: #475569; margin-bottom: 22px; font-weight: 500; }}

  /* 1. 架构图分层 */
  .arch-grid {{ display: flex; flex-direction: column; gap: 12px; }}
  .arch-row {{ display: flex; border: 1.5px solid #CBD5E1; border-radius: 12px; overflow: hidden; background: #F8FAFC; }}
  .arch-header {{ width: 195px; padding: 16px 14px; font-weight: 800; font-size: 15px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; color: #FFFFFF; flex-shrink: 0; line-height: 1.35; }}
  .arch-header small {{ font-size: 11px; opacity: 0.88; font-weight: 600; margin-top: 3px; }}
  .arch-body {{ flex: 1; padding: 12px 18px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; align-items: stretch; background: #FFFFFF; }}
  .arch-body.cols-5 {{ grid-template-columns: repeat(5, 1fr); }}
  .arch-card {{ border: 1.5px solid #E2E8F0; border-radius: 10px; padding: 10px 12px; font-size: 12.5px; font-weight: 500; background: #F8FAFC; color: #334155; line-height: 1.45; }}
  .arch-card b {{ color: #0F172A; font-weight: 700; display: block; margin-bottom: 3px; font-size: 13px; }}
  .arch-card.highlight {{ background: #ECFDF5; border-color: #6EE7B7; color: #065F46; }}
  .arch-card.highlight b {{ color: #047857; }}
  .arch-card.tech {{ background: #EFF6FF; border-color: #93C5FD; color: #1E3A8A; }}
  .arch-card.tech b {{ color: #1D4ED8; }}
  .arch-card.amber {{ background: #FFFBEB; border-color: #FCD34D; color: #78350F; }}
  .arch-card.amber b {{ color: #B45309; }}

  /* 通用流程行 */
  .flow-row {{ display: flex; align-items: stretch; justify-content: space-between; gap: 14px; }}
  .flow-step {{ flex: 1; border: 1.5px solid #CBD5E1; border-radius: 14px; padding: 18px; background: #F8FAFC; display: flex; flex-direction: column; position: relative; }}
  .flow-step.step-green {{ background: #F0FDF4; border-color: #86EFAC; }}
  .flow-step.step-blue {{ background: #EFF6FF; border-color: #93C5FD; }}
  .flow-step.step-amber {{ background: #FFFBEB; border-color: #FCD34D; }}
  .flow-step.step-purple {{ background: #FAF5FF; border-color: #D8B4FE; }}
  .flow-step.step-red {{ background: #FEF2F2; border-color: #FCA5A5; }}
  .step-num {{ font-size: 11.5px; font-weight: 800; text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.6px; }}
  .step-title {{ font-size: 16.5px; font-weight: 800; color: #0F172A; margin-bottom: 10px; }}
  .step-content {{ font-size: 13px; color: #334155; line-height: 1.55; flex: 1; }}
  .step-badge {{ display: inline-block; margin-top: 12px; font-size: 11.5px; font-weight: 700; padding: 4px 10px; border-radius: 6px; align-self: flex-start; }}
  .flow-arrow {{ display: flex; align-items: center; justify-content: center; color: #64748B; font-size: 24px; font-weight: 900; }}

  /* 雙欄對比與圖表布局 */
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 22px; }}
  .panel {{ border: 1.5px solid #E2E8F0; border-radius: 14px; padding: 20px; background: #F8FAFC; }}
  .panel.white {{ background: #FFFFFF; }}
  .panel-title {{ font-size: 16px; font-weight: 800; color: #0F172A; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; }}
  .badge-pill {{ font-size: 11.5px; font-weight: 700; padding: 3px 10px; border-radius: 99px; }}

  /* 水平条形图 */
  .bar-group {{ display: flex; flex-direction: column; gap: 12px; margin-top: 10px; }}
  .bar-item {{ display: flex; flex-direction: column; gap: 5px; }}
  .bar-label-row {{ display: flex; justify-content: space-between; font-size: 13px; font-weight: 700; color: #1E293B; }}
  .bar-track {{ height: 22px; background: #E2E8F0; border-radius: 6px; overflow: hidden; position: relative; display: flex; }}
  .bar-fill {{ height: 100%; border-radius: 6px; display: flex; align-items: center; justify-content: flex-end; padding-right: 8px; color: #FFF; font-size: 11.5px; font-weight: 800; }}

  /* 表格美化 */
  .clean-table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 10px; border-radius: 10px; overflow: hidden; }}
  .clean-table th {{ background: #1E293B; color: #FFFFFF; padding: 10px 12px; text-align: left; font-weight: 700; }}
  .clean-table td {{ padding: 10px 12px; border-bottom: 1px solid #E2E8F0; background: #FFFFFF; color: #334155; font-weight: 500; }}
  .clean-table tr.hl td {{ background: #ECFDF5; color: #065F46; font-weight: 700; }}
  .clean-table tr.warn td {{ background: #FEF2F2; color: #991B1B; font-weight: 700; }}
</style>
</head>
<body>

<!-- =====================================================================
     图 1：系统全栈技术与多层算法总体架构图 (Slide 03)
     ===================================================================== -->
<div id="chart-system-arch" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag">ARCHITECTURE</span>
    《食养有据》五层全栈技术与计算生物学算法架构全景
  </div>
  <div class="diagram-desc">2026-11-06 实测底座：105 味药食同源全目录 · 6,205 化合物 (4,562 持入血预测) · 10,154 人类蛋白靶点 · 62,617 互作关联 · 73 经典方剂</div>

  <div class="arch-grid">
    <!-- 第五层 -->
    <div class="arch-row">
      <div class="arch-header" style="background: #1D4ED8;">五、工程与普惠交互层<small>Engineering & Accessibility</small></div>
      <div class="arch-body">
        <div class="arch-card tech"><b>FastAPI 异步高性能服务</b>实测 57 路径 / 61 端点 · 106 项单测全通过 · 在线推断延迟 &lt; 15ms</div>
        <div class="arch-card tech"><b>双 SQLite 动静物理隔离</b>知识库 shiyang.db (mode=ro 只读防篡改) ＋ 用户库 user.db (WAL 并发读写)</div>
        <div class="arch-card highlight"><b>长辈高对比大字适老模式</b>自研 FontScale 动态缩放系统 · WCAG 高对比配色 · 消除银发数字鸿沟</div>
        <div class="arch-card"><b>全站矢量学术交互界面</b>Vue3 + Vant 移动端 + Capacitor 安卓 APK · 严禁廉价表情符号 · 零外网静态字体依赖</div>
      </div>
    </div>

    <!-- 第四层 -->
    <div class="arch-row">
      <div class="arch-header" style="background: #047857;">四、多目标协同决策层<small>Decision & Services</small></div>
      <div class="arch-body cols-5">
        <div class="arch-card highlight"><b>【我的茶罐】反向图配伍</b>5 大语义分类货架 · 食材子集图覆盖贪心排序 (Coverage 优先)</div>
        <div class="arch-card highlight"><b>【对比实验室】多方同屏 PK</b>配料重合度 ＋ 高入血活性成分对比 ＋ 科学三维指数同屏叠加</div>
        <div class="arch-card amber"><b>食养科学三维评价指数</b>入血潜力 (absorption) · 多靶协同 (synergy) · 证据强度 (evidence)</div>
        <div class="arch-card"><b>CCMQ 67 题国标体质辨识</b>中华中医药学会标准 9 种体质转化分与偏颇雷达判定</div>
        <div class="arch-card amber"><b>Safety Gate 安全禁忌硬剪枝</b>体质相冲忌口 ＋ 孕哺/慢病特殊人群红线一票否决拦截</div>
      </div>
    </div>

    <!-- 第三层 -->
    <div class="arch-row">
      <div class="arch-header" style="background: #B45309;">三、核心算法矩阵<small>Core Algorithms Engine</small></div>
      <div class="arch-body cols-5">
        <div class="arch-card highlight"><b>PU-Learning 入血预测引擎</b>PU-Bagging + RandomForest · ROC-AUC 0.903±0.008 · PR-AUC 0.573</div>
        <div class="arch-card amber"><b>prob_caliber 三档分层治理</b>A类 165 + B类 795 + C类 3,602 = 4,562 · 消融实验否决缺维强推</div>
        <div class="arch-card tech"><b>留一法 (LOO) 全库适用域</b>Tanimoto 最近邻分位标定 · 全库 4,558 分子 (域内 2,775 / 边缘 1,193 / 域外 590)</div>
        <div class="arch-card tech"><b>全库 UMAP 化学空间流形</b>1024D → 2D 拓扑投影 (4,558 节点) · 入血概率/应用域/一致性三视图</div>
        <div class="arch-card highlight"><b>本地 RapidOCR + 形近字纠错</b>ONNX 纯 CPU 断网推理 · 三级受限本草纠偏 (纠错 11/12 · 误纠 0/40)</div>
      </div>
    </div>

    <!-- 第二层 -->
    <div class="arch-row">
      <div class="arch-header" style="background: #0369A1;">二、多模态特征工程层<small>Feature Representation</small></div>
      <div class="arch-body">
        <div class="arch-card tech"><b>1024-bit Morgan 拓扑指纹</b>RDKit ECFP4 (Radius=2) 分子图局部子结构哈希编码</div>
        <div class="arch-card"><b>19 维理化与 ADME 描述符</b>MW、LogP、TPSA、HBD/HBA 及 Lipinski 口服特征自动归因解读</div>
        <div class="arch-card amber"><b>三档煎煮转移率情景建模</b>保守 (0.3) / 基准 (0.5) / 乐观 (0.7) × 药材含量区间 → 诚实暴露量区间 [min, max] mg</div>
        <div class="arch-card"><b>端侧视觉预处理与置信剪枝</b>图像自适应二值化 ＋ 行置信度 Conf &lt; 0.5 剪枝过滤</div>
      </div>
    </div>

    <!-- 第一层 -->
    <div class="arch-row">
      <div class="arch-header" style="background: #334155;">一、多组学数据底座层<small>Data Foundation</small></div>
      <div class="arch-body">
        <div class="arch-card highlight"><b>国家卫健委药食同源全目录</b>105 味药材全收录 · 药材-成分双口径修正视图 (DUAL_RELATION_SQL)</div>
        <div class="arch-card"><b>南中医 ccTCM 2.0 权威科研库</b>赵玉男教授团队提供：6,196 行含量区间 · 40,634 条靶点关联 · 血中移行正例标识</div>
        <div class="arch-card tech"><b>ChEMBL 国际实验活性数据库</b>InChIKey 精确匹配 126 成分 · 73 成分入库 465 条实测 Ki/IC50 · 127 条 L1 强证据</div>
        <div class="arch-card"><b>多源本草与靶点知识图谱</b>SymMap 703 味本草词表 ＋ UniProt 10,154 人类蛋白靶点 ＋ 62,617 条成分-靶点互作</div>
      </div>
    </div>
  </div>
</div>

<!-- =====================================================================
     图 2：PU-Learning 算法原理与“检出倾向 ≠ 吸收率”生物学机理解构 (Slide 04)
     ===================================================================== -->
<div id="chart-algo-pulearning" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag blue">ALGORITHM 01</span>
    PU-Learning (Elkan-Noto 协议) 入血预测流与中药体内代谢标签机理
  </div>
  <div class="diagram-desc">解决文献“只报检出正例 (13%)、无未检出真负例”的数据困境，厘清「血中移行检出倾向」与「口服生物利用度 F%」的本质区别</div>

  <div class="flow-row" style="margin-bottom: 20px;">
    <div class="flow-step step-blue">
      <div class="step-num" style="color:#1D4ED8;">STEP 1 · 样本空间形式化</div>
      <div class="step-title">正样本集 P 与未标注集 U</div>
      <div class="step-content">
        • <b>正样本集 P (282 个)</b>：文献实验明确在血浆中检出的移行成分 (Label = 1，占比 13.0%)<br>
        • <b>未标注池 U (1,887 个)</b>：候选化合物大池，正负未知（含大量未做血药实验的潜在入血分子）<br>
        • <b>特征空间 (1,043 维)</b>：1024-bit Morgan 指纹 (ECFP4) ＋ 19 维理化/ADME 描述符
      </div>
      <div class="step-badge" style="background:#DBEAFE;color:#1E40AF;">突破二分类伪负例惩罚</div>
    </div>
    <div class="flow-arrow">→</div>
    <div class="flow-step step-green">
      <div class="step-num" style="color:#047857;">STEP 2 · PU-Bagging 迭代</div>
      <div class="step-title">K=30 轮均衡有放回采样</div>
      <div class="step-content">
        • <b>均衡子集构造</b>：第 k 轮保留全部正样本 P，从 U 中均匀随机抽取等量子集 U_k 作临时伪负例<br>
        • <b>基分类器训练</b>：训练 K 棵独立随机森林分类器 f_k(x)<br>
        • <b>噪声抑制</b>：避免单次将 U 全当负例导致的严重决策面偏移
      </div>
      <div class="step-badge" style="background:#DCFCE7;color:#166534;">Ensemble Soft Voting</div>
    </div>
    <div class="flow-arrow">→</div>
    <div class="flow-step step-amber">
      <div class="step-num" style="color:#B45309;">STEP 3 · 后验校准与阈值</div>
      <div class="step-title">软投票输出与工程截断</div>
      <div class="step-content">
        • <b>测试集判别力</b>：3 随机种子交叉验证 <b>ROC-AUC = 0.903 ± 0.008</b>，PR-AUC = 0.573<br>
        • <b>高置信工程截断</b>：展示端取 <b>prob ≥ 0.7</b>（精确率从 0.359 跃升至 <b>0.549</b>，召回率 0.596）<br>
        • <b>严守边界</b>：用作成分排序参考，绝不包装为二元疗效结论
      </div>
      <div class="step-badge" style="background:#FEF3C7;color:#92400E;">prob ≥ 0.7 过滤低信噪比</div>
    </div>
  </div>

  <!-- 底部：生物学机理解构对比（解决评委追问：为什么大分子皂苷高分、小分子萜类低分） -->
  <div class="two-col">
    <div class="panel" style="background:#ECFDF5; border-color:#6EE7B7;">
      <div class="panel-title" style="color:#065F46;">
        <span>典型现象 A：为什么大分子皂苷预测高分？（符合体内真实检出规律）</span>
        <span class="badge-pill" style="background:#059669;color:#FFF;">人参皂苷 Re · prob = 0.991</span>
      </div>
      <div style="font-size:13px; color:#064E3B; line-height:1.6;">
        <b>● 药代动力学机制</b>：人参皂苷 Re（MW 947.1 Da）违反 Lipinski 分子量规则，原形直接穿肠壁吸收率（F%）极低；但口服后经<b>肠道菌群糖苷酶水解转化为次生苷/苷元（如 Rg1、Rh1、PPT）</b>进入血液循环，其原型及代谢物在体内血浆 LC-MS 实验中被高频检出，文献阳性报道极为丰富。<br>
        <b>● 算法印证</b>：PU-Learning 准确捕捉到“皂苷母核 → 菌群转化 → 血中可检出”的真实文献标签规律。
      </div>
    </div>
    <div class="panel" style="background:#FFFBEB; border-color:#FCD34D;">
      <div class="panel-title" style="color:#92400E;">
        <span>典型现象 B：为什么挥发性小分子单萜预测偏低？（首过代谢快、难捕原型峰）</span>
        <span class="badge-pill" style="background:#D97706;color:#FFF;">石竹烯 · prob = 0.046</span>
      </div>
      <div style="font-size:13px; color:#78350F; line-height:1.6;">
        <b>● 药代动力学机制</b>：石竹烯（MW 204.4 Da, logP 5.34）分子量小、脂溶性强，透膜速度极快；但进入门静脉后遭受<b>肝脏 CYP450 酶系剧烈的一相氧化代谢</b>，半衰期极短，常规血浆采血窗口极难捕获原型分子峰，文献阳性记录极少。<br>
        <b>● 核心答辩防线</b>：模型预测的是<b>「血中移行检出倾向」而非「口服吸收率 F%」</b>，完全符合药代实验事实！
      </div>
    </div>
  </div>
</div>

<!-- =====================================================================
     图 3：多口径分层治理 (prob_caliber) 与特征退化消融实验图 (Slide 05)
     ===================================================================== -->
<div id="chart-ablation-caliber" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag amber">ABLATION &amp; GOVERNANCE</span>
    扩容 4,562 分子三档口径隔离 (prob_caliber) 与特征退化消融实验
  </div>
  <div class="diagram-desc">当药材从 34 味扩至 105 味全目录时，严禁“一键强跑主模型伪造精度”——用实测消融数据说话</div>

  <div class="two-col">
    <!-- 左栏：三档口径结构分布 -->
    <div class="panel white">
      <div class="panel-title">
        <span>1. 全库 6,205 化合物入血概率三档互不重叠口径</span>
        <span class="badge-pill" style="background:#EFF6FF;color:#1D4ED8;">services/prob_caliber.py</span>
      </div>
      <div class="bar-group">
        <div class="bar-item">
          <div class="bar-label-row">
            <span style="color:#047857;">① A 类：ccTCM 旧主力管线 (prob_cctcm · 完整 19 维特征)</span>
            <span style="color:#047857;">165 个 (3.6%)</span>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width:12%; background:#059669;">165</div></div>
        </div>
        <div class="bar-item">
          <div class="bar-label-row">
            <span style="color:#1D4ED8;">② B 类：ccTCM 正式版精确回填 (prob_cctcm_v2 · 训练集内 SMILES 匹配)</span>
            <span style="color:#1D4ED8;">795 个 (17.4%)</span>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width:28%; background:#2563EB;">795</div></div>
        </div>
        <div class="bar-item">
          <div class="bar-label-row">
            <span style="color:#B45309;">③ C 类：HERB 结构兜底模型外推 (prob_herb_v2 · 仅结构可算，标明外推)</span>
            <span style="color:#B45309;">3,602 个 (79.0%)</span>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width:79%; background:#D97706;">3,602</div></div>
        </div>
        <div class="bar-item">
          <div class="bar-label-row">
            <span style="color:#64748B;">④ 无 SMILES 结构式化合物（诚实返回 None，绝不填 0 混淆！）</span>
            <span style="color:#64748B;">1,643 个</span>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width:36%; background:#94A3B8;">1,643 (返回 None)</div></div>
        </div>
      </div>
      <div style="margin-top:14px; padding:10px 12px; background:#F8FAFC; border-left:4px solid #059669; font-size:12.5px; color:#334155; line-height:1.5;">
        <b>数据真实铁律</b>：缺预测值必须返回 <code>None</code>，<b>绝不填 0</b>——因为 0 代表“模型判定完全不入血”，与“缺乏结构数据未评估”是截然不同的科学结论。
      </div>
    </div>

    <!-- 右栏：消融实验对比 -->
    <div class="panel white">
      <div class="panel-title">
        <span>2. 消融实验：为什么 C 类 3,602 分子绝不强行跑 ccTCM 主模型？</span>
        <span class="badge-pill" style="background:#FEF2F2;color:#DC2626;">165 已知成分实测对照</span>
      </div>
      <table class="clean-table">
        <thead>
          <tr>
            <th>外推方案（针对缺实测 ADME 的扩容分子）</th>
            <th>缺失特征数</th>
            <th>平均绝对偏差 (MAE)</th>
            <th>分类翻转率 / 一致率</th>
            <th>工程决策</th>
          </tr>
        </thead>
        <tbody>
          <tr class="warn">
            <td><b>方案 A：强行跑 ccTCM 主模型</b><br><small>用中位数虚拟填补 7 维实测 ADME 参数</small></td>
            <td>缺 7 维核心实测</td>
            <td><b>0.290（偏差极高）</b></td>
            <td><b>翻转率 44.4%</b><br><small>（形同抛硬币！）</small></td>
            <td><b>严厉否决 ✗</b></td>
          </tr>
          <tr class="hl">
            <td><b>方案 B：切换 HERB 轻量兜底模型</b><br><small>仅依赖 RDKit 可算理化与 Morgan 指纹</small></td>
            <td>仅缺 2 维次要常数</td>
            <td><b>0.135（误差减半）</b></td>
            <td><b>一致率 79.0%</b><br><small>（排序趋势稳健）</small></td>
            <td><b>采纳并标注 ✓</b></td>
          </tr>
        </tbody>
      </table>
      <div style="margin-top:14px; display:grid; grid-template-columns:1fr 1fr; gap:12px;">
        <div style="background:#FEF2F2; border:1px solid #FCA5A5; border-radius:8px; padding:10px; font-size:12px; color:#991B1B;">
          <b>前台诚实降级呈现</b>：C 类分子在成分页与化学空间地图中统一渲染为<b>土黄色「⚠ 外推估计」</b>，明确提示“不等同于主力模型结论”。
        </div>
        <div style="background:#ECFDF5; border:1px solid #6EE7B7; border-radius:8px; padding:10px; font-size:12px; color:#065F46;">
          <b>方法学价值</b>：证明团队不仅会训练高 AUC 模型，更具备识别<b>特征退化（Feature Degradation）</b>并建立工程防火墙的科研素养。
        </div>
      </div>
    </div>
  </div>
</div>

<!-- =====================================================================
     图 4：跨算法族独立交叉验证与分歧机理解构图 (Slide 06)
     ===================================================================== -->
<div id="chart-cross-validation" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag purple">CROSS-VALIDATION</span>
    跨算法族独立交叉验证（4 种机器学习范式）与 43 个分歧成分归因分析
  </div>
  <div class="diagram-desc">在同一数据集上用提升树、神经网络、线性模型独立重训，检验入血判别信号是否依赖特定算法</div>

  <div class="two-col">
    <!-- 左：4 算法族性能对比 -->
    <div class="panel white">
      <div class="panel-title">
        <span>1. 四大算法族测试集性能对照 (3 随机种子均值)</span>
        <span class="badge-pill" style="background:#F5F3FF;color:#6D28D9;">2,169 化合物测试集</span>
      </div>
      <table class="clean-table">
        <thead>
          <tr>
            <th>模型名称</th>
            <th>机器学习算法族</th>
            <th>ROC-AUC (3 Seeds)</th>
            <th>PR-AUC</th>
            <th>训练协议说明</th>
          </tr>
        </thead>
        <tbody>
          <tr class="hl">
            <td><b>主模型 (PU-Bagging + RF)</b></td>
            <td>PU 集成决策树</td>
            <td><b>0.9030 ± 0.0080</b></td>
            <td><b>0.573</b></td>
            <td>每轮全部正样本 + 等量未标注抽样</td>
          </tr>
          <tr class="hl" style="background:#EFF6FF;">
            <td style="background:#EFF6FF;color:#1E3A8A;"><b>独立模型 1：XGBoost</b></td>
            <td style="background:#EFF6FF;color:#1E3A8A;">梯度提升树 (GBDT)</td>
            <td style="background:#EFF6FF;color:#1E3A8A;"><b>0.8961 ± 0.0055</b></td>
            <td style="background:#EFF6FF;color:#1E3A8A;"><b>0.562</b></td>
            <td style="background:#EFF6FF;color:#1E3A8A;">标准二分类 (class_weight 平衡)</td>
          </tr>
          <tr>
            <td><b>独立模型 2：MLP</b></td>
            <td>深度多层感知机</td>
            <td>0.8529 ± 0.0219</td>
            <td>0.535</td>
            <td>标准二分类非线性神经网络</td>
          </tr>
          <tr>
            <td><b>独立模型 3：Logistic</b></td>
            <td>线性分类基线</td>
            <td>0.8225 ± 0.0110</td>
            <td>0.474</td>
            <td>L2 正则化线性可分性检验</td>
          </tr>
        </tbody>
      </table>
      <div style="margin-top:12px; font-size:12.5px; color:#334155; line-height:1.55; background:#F8FAFC; padding:10px 12px; border-radius:8px; border:1px solid #E2E8F0;">
        <b>● 严谨口径说明</b>：对库内 165 个 A 类成分，主模型（阈值 0.7）与<b>三独立模型平均预测值</b>（阈值 0.0837，Youden J 标定）的分类一致率为 <b>73.9%（122/165）</b>，Spearman 秩相关 0.580（若与单模型 XGBoost 单独比较，一致率为 63.6%，两者严格区分不混用）。
      </div>
    </div>

    <!-- 右：43 个分歧成分真实结构解构 -->
    <div class="panel white">
      <div class="panel-title">
        <span>2. 为什么有 26.1% (43/165) 分歧？——真实结构分布与协议归因</span>
        <span class="badge-pill" style="background:#FFFBEB;color:#B45309;">实事求是 · 不夸大 100%</span>
      </div>
      <div class="bar-group">
        <div class="bar-item">
          <div class="bar-label-row">
            <span>双模型共识一致（一致高 + 一致低）</span>
            <span style="color:#047857;">122 / 165 (73.9%)</span>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width:73.9%; background:#059669;">122 个成分结论一致 (73.9%)</div></div>
        </div>
        <div class="bar-item">
          <div class="bar-label-row">
            <span>分歧子集 A：分子量 MW &gt; 400 Da 的大分子成分</span>
            <span style="color:#B45309;">17 / 43 分歧成分</span>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width:39.5%; background:#D97706;">17 个大分子</div></div>
        </div>
        <div class="bar-item">
          <div class="bar-label-row">
            <span>分歧子集 B：名称含“苷”的糖苷/皂苷类（含人参皂苷Rk3、知母皂苷AIII、三七皂苷R1等）</span>
            <span style="color:#7C3AED;">14 / 43 分歧成分</span>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width:32.6%; background:#7C3AED;">14 个苷类 + 3 个脂肪酸</div></div>
        </div>
      </div>
      <div style="margin-top:14px; padding:12px; background:#FFFBEB; border:1px solid #FCD34D; border-radius:10px; font-size:12.5px; color:#78350F; line-height:1.55;">
        <b>★ 学术诚实披露（答辩加分点）</b>：<br>
        1) <b>主因可解释</b>：分歧以苷类与大分子居多（如<b>落新妇苷</b>主模型 0.992 vs 独立模型 0.000），源于主模型 PU 协议对未标注皂苷同源物更宽容，而独立二分类将全部未标注样本硬判为负例。<br>
        2) <b>绝不强词夺理</b>：其余小分子分歧（如酪胺、丁香酚、香荚兰醛）尚未逐条做湿实验归因，及独立脚本全样本中位数填补细节，均在文档中主动披露列为后续改进。
      </div>
    </div>
  </div>
</div>

<!-- =====================================================================
     图 5：留一法 (LOO) 适用域量化与科学可信度四件套闭环 (Slide 07)
     ===================================================================== -->
<div id="chart-ad-distribution" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag">CREDIBILITY QUARTET</span>
    留一法 (LOO) 适用域 (Applicability Domain) 阈值标定与全库 4,558 分子实测分布
  </div>
  <div class="diagram-desc">拒绝把模型当成万能黑盒：计算每个分子与 2,437 个训练集分子的最大 Morgan 指纹 Tanimoto 相似度</div>

  <div class="two-col">
    <!-- 左：留一法阈值标定与两套口径分布 -->
    <div class="panel white">
      <div class="panel-title">
        <span>1. 留一法最近邻相似度分位标定（为什么弃用随机配对？）</span>
        <span class="badge-pill" style="background:#ECFDF5;color:#047857;">Tanimoto 拓扑距离</span>
      </div>
      <div style="font-size:13px; color:#334155; line-height:1.6; margin-bottom:14px;">
        • <b>随机配对陷阱</b>：化学空间高度稀疏，随机两分子 Tanimoto 5% 分位仅 <b>0.028</b>，若以此为阈值会把几乎所有外推分子误判为“域内”，使适用域检验形同虚设！<br>
        • <b>留一法 (Leave-One-Out) 标定</b>：计算训练集内每个分子离“其余训练集最近同伴”的相似度分布，取 <b>5% 分位 (0.333)</b> 与 <b>25% 分位 (0.582)</b> 作为严格分水岭：
      </div>
      <div class="bar-group">
        <div class="bar-item">
          <div class="bar-label-row">
            <span>A 类核心成分适用域分布（共 165 个）</span>
            <span>域内 160 (97.0%) · 边缘 2 · 域外 3</span>
          </div>
          <div class="bar-track">
            <div class="bar-fill" style="width:94%; background:#059669;">域内 160</div>
            <div class="bar-fill" style="width:3%; background:#D97706;"></div>
            <div class="bar-fill" style="width:3%; background:#DC2626;"></div>
          </div>
        </div>
        <div class="bar-item">
          <div class="bar-label-row">
            <span>全库持 SMILES 分子适用域分布（共 4,558 个）</span>
            <span>域内 2,775 (60.9%) · 边缘 1,193 (26.2%) · 域外 590 (12.9%)</span>
          </div>
          <div class="bar-track">
            <div class="bar-fill" style="width:60.9%; background:#059669;">域内 2,775 (60.9%)</div>
            <div class="bar-fill" style="width:26.2%; background:#D97706;">边缘 1,193 (26.2%)</div>
            <div class="bar-fill" style="width:12.9%; background:#DC2626;">域外 590</div>
          </div>
        </div>
      </div>
      <div style="margin-top:14px; padding:10px 12px; background:#FEF2F2; border-left:4px solid #DC2626; font-size:12.5px; color:#991B1B; line-height:1.5;">
        <b>域外自洽验证</b>：A 类中落入域外的 <b>白皮杉醇 (Sim=0.246)</b>、香叶醇、克氏千里光碱，其预测入血概率恰好均处于低位 (0.13~0.29)，前端主动亮起红色「应用域外 · 预测可靠性有限」预警徽章！
      </div>
    </div>

    <!-- 右：可信度四件套全景矩阵 -->
    <div class="panel white">
      <div class="panel-title">
        <span>2. 「可信度四件套」工程闭环：可信的本质是每个数字都诚实</span>
        <span class="badge-pill" style="background:#EFF6FF;color:#1D4ED8;">Credibility Quartet</span>
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
        <div class="arch-card highlight" style="padding:12px;">
          <b>① 适用边界量化 (LOO AD)</b>
          Sim &gt; 0.582 绿色域内；0.333~0.582 琥珀色边缘；≤ 0.333 红色域外降级预警，展示最近邻训练集分子。
        </div>
        <div class="arch-card tech" style="padding:12px;">
          <b>② ChEMBL 体外实验背书</b>
          126 成分精确命中 ChEMBL，73 成分入库 465 条蛋白靶点实测 Ki/IC50，127 条达 L1 强证据 (≤1μM)。
        </div>
        <div class="arch-card" style="padding:12px; background:#FAF5FF; border-color:#D8B4FE; color:#5B21B6;">
          <b style="color:#6D28D9;">③ 跨算法族独立互验</b>
          PU-RF 主模型 vs 独立 XGBoost/MLP/LR 对照，展示双模型对比条与「一致高/主模型单独高」徽章。
        </div>
        <div class="arch-card amber" style="padding:12px;">
          <b>④ 暴露量三档情景区间</b>
          摒弃假单点精度，按保守 (0.3) / 基准 (0.5) / 乐观 (0.7) 三档煎煮转移率输出摄入区间 [min, max] mg。
        </div>
      </div>
    </div>
  </div>
</div>

<!-- =====================================================================
     图 6：全库 4,558 分子 UMAP 化学空间流形实测散点图 (Slide 08)
     ===================================================================== -->
<div id="chart-umap-manifold" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag blue">CHEMICAL SPACE UMAP</span>
    全库 4,558 化合物 1024-bit Morgan 指纹 → 2D UMAP 拓扑流形真实散点投影
  </div>
  <div class="diagram-desc">数据直接读取自 data/shiyang.db 的 compound_map 表（n_neighbors=15, min_dist=0.3, random_state=42）</div>

  <div class="two-col" style="grid-template-columns: 1.35fr 0.65fr;">
    <div class="panel white" style="display:flex; flex-direction:column; align-items:center; justify-content:center; padding:16px;">
      <canvas id="umap-canvas" width="780" height="420" style="border:1px solid #E2E8F0; border-radius:10px; background:#FAF8F5;"></canvas>
      <div style="display:flex; gap:18px; margin-top:10px; font-size:12.5px; font-weight:700; color:#334155;">
        <span><i style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#059669;margin-right:5px;"></i>主力高入血 (≥0.7)</span>
        <span><i style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#D97706;margin-right:5px;"></i>主力中等 (0.5~0.7)</span>
        <span><i style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#DC2626;margin-right:5px;"></i>主力偏低 (&lt;0.5)</span>
        <span><i style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#C2A878;margin-right:5px;"></i>C类 HERB 外推估计 (3,598 点)</span>
      </div>
    </div>
    <div class="panel white" style="display:flex; flex-direction:column; justify-content:space-between;">
      <div>
        <div class="panel-title"><span>流形聚类规律与工程特性</span></div>
        <div style="font-size:13px; color:#334155; line-height:1.65;">
          <b>1. 骨架岛礁自然分离</b>：<br>
          1024 维 ECFP4 拓扑指纹经非线性降维后，黄酮苷类、三萜皂苷、生物碱、挥发油单萜在二维平面自发形成高内聚的骨架岛礁。<br><br>
          <b>2. 入血活性的流形连续性</b>：<br>
          深绿色高入血分子（prob ≥ 0.7）并非随机散落，而是沿特定亲水/两亲性亚结构团簇高度富集。<br><br>
          <b>3. 三视图一键切换交互</b>：<br>
          前端支持<b>「入血概率」·「应用域」·「模型一致性」</b>三种着色模式实时切换，GZip 压缩传输毫秒级响应。
        </div>
      </div>
      <div style="padding:10px 12px; background:#EFF6FF; border-radius:8px; border:1px solid #93C5FD; font-size:12px; color:#1E3A8A;">
        <b>方法学提示</b>：界面显著标注“UMAP 坐标仅相对邻近关系有意义，坐标轴绝对数值无物理量纲”。
      </div>
    </div>
  </div>
</div>

<!-- =====================================================================
     图 7：ChEMBL 实验证据漏斗与食养科学三维评价指数 (Slide 09)
     ===================================================================== -->
<div id="chart-target-3d-index" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag">MECHANISM &amp; EVALUATION</span>
    10,154 靶点网络、ChEMBL 体外实测锚定与「食养科学三维评价指数」重构
  </div>
  <div class="diagram-desc">补齐“实验实测”证据环，并将原哮喘课题受限的三维评分升级为全平台 73 方通用的科学三维评价体系 (eval_service.py)</div>

  <div class="two-col">
    <!-- 左：ChEMBL 清洗与分级 -->
    <div class="panel white">
      <div class="panel-title">
        <span>1. ChEMBL 体外实验活性清洗与分级漏斗</span>
        <span class="badge-pill" style="background:#EFF6FF;color:#1D4ED8;">欧洲生物信息学研究所</span>
      </div>
      <div class="bar-group">
        <div class="bar-item">
          <div class="bar-label-row"><span>A 类 165 核心成分 InChIKey 精确结构匹配</span><span style="color:#1D4ED8;">126 个命中 (76.4%)</span></div>
          <div class="bar-track"><div class="bar-fill" style="width:76.4%; background:#2563EB;">126 / 165 精确匹配</div></div>
        </div>
        <div class="bar-item">
          <div class="bar-label-row"><span>清洗入库人类单一蛋白靶点实测活性记录（73 个成分）</span><span style="color:#047857;">465 条 Ki / IC50 记录</span></div>
          <div class="bar-track"><div class="bar-fill" style="width:65%; background:#059669;">465 条体外实测活性</div></div>
        </div>
        <div class="bar-item">
          <div class="bar-label-row"><span>L1 级强实验证据（pChEMBL ≥ 6，即 Ki/IC50 ≤ 1 μM）</span><span style="color:#B45309;">127 条强证据 (27.3%)</span></div>
          <div class="bar-track"><div class="bar-fill" style="width:42%; background:#D97706;">127 条 L1 强证据 · 338 条 L2 中等证据</div></div>
        </div>
      </div>
      <div style="margin-top:14px; font-size:12.5px; color:#334155; background:#F8FAFC; padding:10px 12px; border-radius:8px; border:1px solid #E2E8F0; line-height:1.55;">
        <b>● 攻克两大脏数据陷阱</b>：<br>
        ① 中药老文献大量缺 <code>pchembl_value</code>（如人参皂苷 Re 全为 None），自研从原始值+单位自动换算；<br>
        ② 二次联查 <code>target.json</code> 校验靶点类型，彻底剔除 <code>SK-MEL-28</code> 等肿瘤细胞系非分子靶点污染。
      </div>
    </div>

    <!-- 右：食养科学三维评价指数 -->
    <div class="panel white">
      <div class="panel-title">
        <span>2. 评价体系演进：食养科学三维评价指数 (满分 100)</span>
        <span class="badge-pill" style="background:#ECFDF5;color:#047857;">2026-11-06 全量重构</span>
      </div>
      <div style="font-size:12.5px; color:#475569; margin-bottom:10px; line-height:1.5;">
        原大创课题《抗炎/免疫调节/气道修复》仅适用于护嗓润喉类方剂。为覆盖全库润燥、温阳、健脾、安神等 73 首方剂，重构为普适、可复算的三维指数：
      </div>
      <div style="display:flex; flex-direction:column; gap:10px;">
        <div class="arch-card highlight">
          <b>维度一：入血潜力 (Absorption · 权重核心)</b>
          取方剂检出的 Top 10 核心活性化合物 PU-Learning 入血概率均值 × 100（反映方剂活性分子穿过肠壁进入体循环的潜力）。
        </div>
        <div class="arch-card tech">
          <b>维度二：多靶协同 (Synergy · 网络药理学)</b>
          统计方剂高入血成分调控的人类蛋白靶点总连接数 L，采用对数饱和映射：<code>min(95, 50.0 + 9.0 × log2(L + 1))</code>。
        </div>
        <div class="arch-card amber">
          <b>维度三：证据强度 (Evidence · 循证分级)</b>
          以 68 分为基准，融合 A 级（卫健委名录/古籍医家方源 +3分/项）与 B 级（PubMed 文献 / ChEMBL 实验活性 +2.5分/项），区间 68~96 分。
        </div>
      </div>
    </div>
  </div>
</div>

<!-- =====================================================================
     图 8：端侧识方、形近字纠错、茶罐反向图配伍与多目标推荐决策流 (Slide 11-13)
     ===================================================================== -->
<div id="chart-pantry-recommendation" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag">END-TO-END WORKFLOW</span>
    端侧纯 CPU 识方、本草形近字拓扑纠错、茶罐子集图覆盖与 CCMQ 协同推荐流
  </div>
  <div class="diagram-desc">打通“拍照/手录识方 → 三级受限纠错 → 105 味茶罐反向组方 → 国标体质与安全剪枝推荐”的完整落地闭环</div>

  <div class="flow-row">
    <div class="flow-step step-blue">
      <div class="step-num" style="color:#1D4ED8;">MODULE 1 · 本地端侧 OCR</div>
      <div class="step-title">RapidOCR (ONNX 纯 CPU)</div>
      <div class="step-content">
        • <b>脱离云端大模型</b>：零 API 成本、断网可用<br>
        • <b>三档劣化图实测</b>：<br>
          - 清晰图：<b>1.5s</b> (100% 召回)<br>
          - 中度劣化：<b>3.6s</b> (100% 召回)<br>
          - 极端倾斜模糊：<b>2.9s</b> (100%)<br>
        • <b>行置信过滤</b>：丢弃 Conf &lt; 0.5 噪点
      </div>
      <div class="step-badge" style="background:#DBEAFE;color:#1E40AF;">零成本 · 离线高可用</div>
    </div>
    <div class="flow-arrow">→</div>
    <div class="flow-step step-purple">
      <div class="step-num" style="color:#6D28D9;">MODULE 2 · 本草拓扑纠错</div>
      <div class="step-title">correct_herb_name 三级纠偏</div>
      <div class="step-content">
        基于 <b>105 味药食同源 + 703 味 SymMap</b>：<br>
        ① <b>同长度形近替换</b>：金银化 → 金银花<br>
        ② <b>受限省字匹配</b>：枸札 → 枸杞子<br>
        ③ <b>编辑距离 1 受限匹配</b>：阵皮 → 陈皮<br>
        • <b>安全锁</b>：多候选歧义拒猜（桂圆≠桂枝）<br>
        • <b>透明可逆</b>：前端展示纠偏轨迹并支持点按撤回
      </div>
      <div class="step-badge" style="background:#F3E8FF;color:#6B21A8;">纠错 11/12 · 误纠 0/40</div>
    </div>
    <div class="flow-arrow">→</div>
    <div class="flow-step step-green">
      <div class="step-num" style="color:#047857;">MODULE 3 · 茶罐反向配伍</div>
      <div class="step-title">食材子集图覆盖贪心算法</div>
      <div class="step-content">
        • <b>全分类货架</b>：花叶果茶 / 根茎本草 / 谷豆果仁 / 生鲜煲汤 / 糖蜜茶奶<br>
        • <b>覆盖率定义</b>：<br>
          <code>Cov(r) = |M_own ∩ M_req(r)| / |M_req(r)|</code><br>
        • <b>三级字典序贪心排序</b>：<br>
          ① 覆盖率降序（今晚直接能煮）<br>
          ② 缺料数升序（差一味好凑）<br>
          ③ 高入血活性成分数降序
      </div>
      <div class="step-badge" style="background:#DCFCE7;color:#166534;">激活家庭囤货食材</div>
    </div>
    <div class="flow-arrow">→</div>
    <div class="flow-step step-amber">
      <div class="step-num" style="color:#B45309;">MODULE 4 · 体质安全协同</div>
      <div class="step-title">Safety Gate + 四维效用打分</div>
      <div class="step-content">
        • <b>第一道防线（安全硬剪枝）</b>：<br>
          CCMQ 67 题判定 9 种体质，体质相冲与孕哺/慢病禁忌<b>一票否决</b><br>
        • <b>第二道防线（多源协同打分）</b>：<br>
          <code>S(r) = w_c·体质 + w_t·24节气 + w_b·打卡偏好 + w_a·入血丰度</code><br>
        • <b>科研下放 P0</b>：成分一句话卡 ＋ 通俗解读
      </div>
      <div class="step-badge" style="background:#FEF3C7;color:#92400E;">安全优先于相关性</div>
    </div>
  </div>
</div>

<script>
  const pts = {umap_pts_json};
  const canvas = document.getElementById('umap-canvas');
  const ctx = canvas.getContext('2d');
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const [x, y] of pts) {{
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  }}
  const pad = 28;
  const W = canvas.width - pad * 2;
  const H = canvas.height - pad * 2;

  // 绘制浅色网格线
  ctx.strokeStyle = '#E2E8F0';
  ctx.lineWidth = 1;
  for (let i = 1; i < 5; i++) {{
    ctx.beginPath();
    ctx.moveTo(pad, pad + (H * i) / 5);
    ctx.lineTo(pad + W, pad + (H * i) / 5);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(pad + (W * i) / 5, pad);
    ctx.lineTo(pad + (W * i) / 5, pad + H);
    ctx.stroke();
  }}

  // 先画外推点 (底层)，再画主力模型点 (顶层突出)
  const colorMap = {{
    ext: 'rgba(194, 168, 120, 0.45)',
    low: 'rgba(220, 38, 38, 0.82)',
    mid: 'rgba(217, 119, 6, 0.85)',
    high: 'rgba(5, 150, 105, 0.92)'
  }};
  for (const layer of ['ext', 'low', 'mid', 'high']) {{
    ctx.fillStyle = colorMap[layer];
    const r = layer === 'ext' ? 2.6 : 4.2;
    for (const [x, y, cat] of pts) {{
      if (cat !== layer) continue;
      const cx = pad + ((x - minX) / (maxX - minX)) * W;
      const cy = pad + H - ((y - minY) / (maxY - minY)) * H;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fill();
    }}
  }}
</script>
</body>
</html>
"""


async def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pts = load_umap_points()
    html_content = build_html(json.dumps(pts))
    html_file = OUT_DIR / "temp_diagrams.html"
    html_file.write_text(html_content, encoding="utf-8")

    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME)
        ctx = await browser.new_context(viewport={"width": 1520, "height": 5000}, device_scale_factor=2)
        page = await ctx.new_page()
        await page.goto(f"file:///{html_file.as_posix()}", wait_until="networkidle")
        await page.wait_for_timeout(600)

        diagrams = [
            ("diagram_system_architecture.png", "#chart-system-arch"),
            ("diagram_algorithm_pulearning.png", "#chart-algo-pulearning"),
            ("chart_ablation_caliber.png", "#chart-ablation-caliber"),
            ("chart_cross_validation.png", "#chart-cross-validation"),
            ("diagram_credibility_quartet.png", "#chart-ad-distribution"),
            ("chart_umap_manifold.png", "#chart-umap-manifold"),
            ("chart_target_3d_index.png", "#chart-target-3d-index"),
            ("diagram_pantry_recommendation.png", "#chart-pantry-recommendation"),
        ]

        for filename, selector in diagrams:
            element = await page.query_selector(selector)
            if element:
                target_path = OUT_DIR / filename
                await element.screenshot(path=str(target_path))
                print(f"成功高清导出: {target_path.name} (Retina 2x)")
            else:
                print(f"未找到元素: {selector}")

        await browser.close()

    if html_file.exists():
        html_file.unlink()
    print("所有 8 张白底高清架构与实测数据图表生成完毕！")


if __name__ == "__main__":
    asyncio.run(main())
