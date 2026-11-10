# -*- coding: utf-8 -*-
"""
生成答辩专用的白底极简风（Minimalist Academic Light）图表与架构图 PNG
设计原则：「少字、大字、高留白、零靶子」——不把容易被评委挑刺的细枝末节写上屏幕，只留核心大数字与直观视觉图！
直接从 data/shiyang.db 读取真实坐标，使用 Playwright Retina 2x 导出至 docs/diagrams/
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
    con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    rows = con.execute("""
        SELECT x, y, prob_cctcm, prob_cctcm_v2, prob_herb_v2
        FROM compound_map
        WHERE x IS NOT NULL AND y IS NOT NULL
    """).fetchall()
    con.close()
    pts = []
    for x, y, p1, p2, ph in rows:
        p_main = p1 if p1 is not None else p2
        if p_main is not None:
            cat = "high" if p_main >= 0.7 else ("mid" if p_main >= 0.5 else "low")
        else:
            cat = "ext"
        pts.append([round(float(x), 3), round(float(y), 3), cat])
    return pts


def build_html(umap_pts_json: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: "Microsoft YaHei", "PingFang SC", sans-serif; }}
  body {{ background: #F1F5F9; color: #0F172A; display: flex; flex-direction: column; gap: 48px; padding: 40px; width: 1400px; }}
  .diagram-container {{ background: #FFFFFF; border: 1.5px solid #E2E8F0; border-radius: 20px; padding: 28px 34px; box-shadow: 0 6px 24px rgba(15,23,42,0.05); }}
  .diagram-title {{ font-size: 25px; font-weight: 800; color: #0F172A; margin-bottom: 18px; display: flex; align-items: center; gap: 12px; }}
  .diagram-tag {{ font-size: 13px; font-weight: 800; padding: 5px 14px; border-radius: 99px; background: #ECFDF5; color: #047857; border: 1.5px solid #6EE7B7; }}
  .diagram-tag.blue {{ background: #EFF6FF; color: #1D4ED8; border-color: #93C5FD; }}
  .diagram-tag.amber {{ background: #FFFBEB; color: #B45309; border-color: #FCD34D; }}
  .diagram-tag.purple {{ background: #F5F3FF; color: #6D28D9; border-color: #C4B5FD; }}

  /* 1. 极简架构图 */
  .arch-grid {{ display: flex; flex-direction: column; gap: 14px; }}
  .arch-row {{ display: flex; border: 1.5px solid #CBD5E1; border-radius: 14px; overflow: hidden; }}
  .arch-header {{ width: 200px; padding: 18px 14px; font-weight: 800; font-size: 17px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; color: #FFFFFF; flex-shrink: 0; }}
  .arch-header small {{ font-size: 12px; opacity: 0.88; font-weight: 600; margin-top: 4px; }}
  .arch-body {{ flex: 1; padding: 14px 20px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; align-items: center; background: #FFFFFF; }}
  .arch-card {{ border: 1.5px solid #E2E8F0; border-radius: 12px; padding: 14px 16px; background: #F8FAFC; text-align: center; }}
  .arch-card b {{ color: #0F172A; font-weight: 800; display: block; margin-bottom: 4px; font-size: 15.5px; }}
  .arch-card span {{ font-size: 13px; color: #475569; font-weight: 600; }}
  .arch-card.highlight {{ background: #ECFDF5; border-color: #6EE7B7; }}
  .arch-card.highlight b {{ color: #047857; }}
  .arch-card.tech {{ background: #EFF6FF; border-color: #93C5FD; }}
  .arch-card.tech b {{ color: #1D4ED8; }}
  .arch-card.amber {{ background: #FFFBEB; border-color: #FCD34D; }}
  .arch-card.amber b {{ color: #B45309; }}

  /* 2. 极简流程块 */
  .flow-row {{ display: flex; align-items: stretch; justify-content: space-between; gap: 16px; }}
  .flow-step {{ flex: 1; border: 1.5px solid #CBD5E1; border-radius: 16px; padding: 22px; background: #F8FAFC; display: flex; flex-direction: column; justify-content: space-between; }}
  .flow-step.step-green {{ background: #F0FDF4; border-color: #86EFAC; }}
  .flow-step.step-blue {{ background: #EFF6FF; border-color: #93C5FD; }}
  .flow-step.step-amber {{ background: #FFFBEB; border-color: #FCD34D; }}
  .flow-step.step-purple {{ background: #FAF5FF; border-color: #D8B4FE; }}
  .step-num {{ font-size: 13px; font-weight: 800; margin-bottom: 6px; letter-spacing: 0.5px; }}
  .step-title {{ font-size: 20px; font-weight: 800; color: #0F172A; margin-bottom: 12px; }}
  .step-list {{ font-size: 15px; color: #334155; line-height: 1.75; font-weight: 600; }}
  .step-badge {{ display: inline-block; margin-top: 14px; font-size: 13.5px; font-weight: 800; padding: 6px 14px; border-radius: 8px; align-self: flex-start; }}
  .flow-arrow {{ display: flex; align-items: center; justify-content: center; color: #64748B; font-size: 28px; font-weight: 900; }}

  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
  .panel {{ border: 1.5px solid #E2E8F0; border-radius: 16px; padding: 24px; background: #FFFFFF; }}
  .panel-title {{ font-size: 18px; font-weight: 800; color: #0F172A; margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; }}
  .badge-pill {{ font-size: 12.5px; font-weight: 800; padding: 4px 12px; border-radius: 99px; }}

  /* 大号进度条 */
  .bar-group {{ display: flex; flex-direction: column; gap: 16px; }}
  .bar-item {{ display: flex; flex-direction: column; gap: 6px; }}
  .bar-label-row {{ display: flex; justify-content: space-between; font-size: 15px; font-weight: 800; color: #1E293B; }}
  .bar-track {{ height: 28px; background: #E2E8F0; border-radius: 8px; overflow: hidden; display: flex; }}
  .bar-fill {{ height: 100%; display: flex; align-items: center; justify-content: flex-end; padding-right: 12px; color: #FFF; font-size: 13.5px; font-weight: 800; }}

  /* 极简大字表格 */
  .clean-table {{ width: 100%; border-collapse: collapse; font-size: 15px; border-radius: 12px; overflow: hidden; }}
  .clean-table th {{ background: #1E293B; color: #FFFFFF; padding: 13px 16px; text-align: left; font-weight: 800; }}
  .clean-table td {{ padding: 13px 16px; border-bottom: 1px solid #E2E8F0; background: #FFFFFF; color: #334155; font-weight: 600; }}
  .clean-table tr.hl td {{ background: #ECFDF5; color: #065F46; font-weight: 800; }}
  .clean-table tr.warn td {{ background: #FEF2F2; color: #991B1B; font-weight: 800; }}
</style>
</head>
<body>

<!-- 图 1：系统五层架构图 (Slide 03) - 极简词块版 -->
<div id="chart-system-arch" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag">ARCHITECTURE</span>
    《食养有据》五层技术与算法总体架构
  </div>
  <div class="arch-grid">
    <div class="arch-row">
      <div class="arch-header" style="background: #1D4ED8;">五、工程与交互层<small>Client &amp; Service</small></div>
      <div class="arch-body">
        <div class="arch-card tech"><b>FastAPI 异步服务</b><span>57 路径 / 61 端点</span></div>
        <div class="arch-card tech"><b>双 SQLite 动静隔离</b><span>只读知识库 + 读写用户库</span></div>
        <div class="arch-card highlight"><b>长辈高对比大字版</b><span>一键适老无障碍缩放</span></div>
        <div class="arch-card"><b>多端应用交付</b><span>Vue3 网页 + 安卓 APK</span></div>
      </div>
    </div>
    <div class="arch-row">
      <div class="arch-header" style="background: #047857;">四、协同决策层<small>Decision Engine</small></div>
      <div class="arch-body">
        <div class="arch-card highlight"><b>我的茶罐反向配伍</b><span>食材子集图覆盖算法</span></div>
        <div class="arch-card highlight"><b>对比实验室</b><span>双槽位多维同屏 PK</span></div>
        <div class="arch-card amber"><b>食养科学三维指数</b><span>入血潜力·多靶协同·证据强度</span></div>
        <div class="arch-card"><b>CCMQ 体质与安全门</b><span>67 题量表 + 禁忌拦截</span></div>
      </div>
    </div>
    <div class="arch-row">
      <div class="arch-header" style="background: #B45309;">三、核心算法层<small>Core Algorithms</small></div>
      <div class="arch-body">
        <div class="arch-card highlight"><b>PU-Learning 入血预测</b><span>ROC-AUC 0.903 ± 0.008</span></div>
        <div class="arch-card amber"><b>三档口径消融治理</b><span>A/B/C 分层 · 4,562 分子</span></div>
        <div class="arch-card tech"><b>留一法适用域 + UMAP</b><span>4,558 分子流形与红牌预警</span></div>
        <div class="arch-card highlight"><b>端侧 OCR + 本草纠偏</b><span>纯 CPU · 纠错率 11/12</span></div>
      </div>
    </div>
    <div class="arch-row">
      <div class="arch-header" style="background: #0369A1;">二、特征表征层<small>Representation</small></div>
      <div class="arch-body">
        <div class="arch-card tech"><b>1024-bit Morgan 指纹</b><span>RDKit 分子拓扑编码</span></div>
        <div class="arch-card"><b>19 维理化描述符</b><span>MW / LogP / Lipinski</span></div>
        <div class="arch-card amber"><b>三档煎煮转移率</b><span>保守 0.3 / 基准 0.5 / 乐观 0.7</span></div>
        <div class="arch-card"><b>端侧视觉预处理</b><span>自适应二值化 + 置信过滤</span></div>
      </div>
    </div>
    <div class="arch-row">
      <div class="arch-header" style="background: #334155;">一、数据底座层<small>Data Foundation</small></div>
      <div class="arch-body">
        <div class="arch-card highlight"><b>卫健委 105 味全目录</b><span>73 首经典食养方剂</span></div>
        <div class="arch-card"><b>ccTCM 2.0 原始库</b><span>6,205 化合物 · 含量区间</span></div>
        <div class="arch-card tech"><b>ChEMBL 体外实测</b><span>465 条活性 · 127 条强证据</span></div>
        <div class="arch-card"><b>人类蛋白靶点网络</b><span>10,154 靶点 · 62,617 关联</span></div>
      </div>
    </div>
  </div>
</div>

<!-- 图 2：PU-Learning 算法流程 (Slide 04) - 极简版 -->
<div id="chart-algo-pulearning" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag blue">ALGORITHM 01</span>
    PU-Learning 入血预测流程与「血中检出倾向」机理
  </div>
  <div class="flow-row" style="margin-bottom: 22px;">
    <div class="flow-step step-blue">
      <div>
        <div class="step-num" style="color:#1D4ED8;">STEP 1 · 样本构造</div>
        <div class="step-title">正例与未标注池</div>
        <div class="step-list">
          • 正样本 P：<b>282 个</b>入血分子<br>
          • 未标注池 U：<b>1,887 个</b>候选分子<br>
          • 特征：<b>1024 位</b> Morgan 指纹
        </div>
      </div>
      <div class="step-badge" style="background:#DBEAFE;color:#1E40AF;">解决“无真负例”痛点</div>
    </div>
    <div class="flow-arrow">→</div>
    <div class="flow-step step-green">
      <div>
        <div class="step-num" style="color:#047857;">STEP 2 · 集成训练</div>
        <div class="step-title">PU-Bagging 采样</div>
        <div class="step-list">
          • <b>30 轮</b>均衡有放回抽样<br>
          • 每轮正例 P + 等量未标注子集<br>
          • 多棵随机森林<b>软投票集成</b>
        </div>
      </div>
      <div class="step-badge" style="background:#DCFCE7;color:#166534;">抑制未标注噪声</div>
    </div>
    <div class="flow-arrow">→</div>
    <div class="flow-step step-amber">
      <div>
        <div class="step-num" style="color:#B45309;">STEP 3 · 预测输出</div>
        <div class="step-title">高置信排序参考</div>
        <div class="step-list">
          • 测试集 <b>ROC-AUC = 0.903</b><br>
          • 展示截断阈值：<b>prob ≥ 0.7</b><br>
          • 用作成分排序，不作二元判定
        </div>
      </div>
      <div class="step-badge" style="background:#FEF3C7;color:#92400E;">精确率提升至 54.9%</div>
    </div>
  </div>
  <div class="two-col">
    <div class="panel" style="background:#ECFDF5; border-color:#6EE7B7; padding:18px 22px;">
      <div class="panel-title" style="color:#065F46; margin-bottom:8px;">
        <span>案例 A：人参皂苷 Re（MW 947 Da）</span>
        <span class="badge-pill" style="background:#059669;color:#FFF;">预测得分 0.991（高）</span>
      </div>
      <div style="font-size:14.5px; color:#064E3B; line-height:1.6; font-weight:600;">
        虽为大分子，但口服后经<b>肠道菌群水解为次生苷入血</b>，血浆实验高频检出。
      </div>
    </div>
    <div class="panel" style="background:#FFFBEB; border-color:#FCD34D; padding:18px 22px;">
      <div class="panel-title" style="color:#92400E; margin-bottom:8px;">
        <span>案例 B：石竹烯（MW 204 Da）</span>
        <span class="badge-pill" style="background:#D97706;color:#FFF;">预测得分 0.046（低）</span>
      </div>
      <div style="font-size:14.5px; color:#78350F; line-height:1.6; font-weight:600;">
        虽为易吸收小分子，但<b>肝脏首过代谢极快</b>，血浆中难捕获原型峰。
      </div>
    </div>
  </div>
</div>

<!-- 图 3：三档口径与消融实验 (Slide 05) - 极简版 -->
<div id="chart-ablation-caliber" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag amber">ABLATION STUDY</span>
    4,562 分子三档口径分层与消融实验对照
  </div>
  <div class="two-col">
    <div class="panel">
      <div class="panel-title">
        <span>1. 入血概率三档互不重叠口径</span>
        <span class="badge-pill" style="background:#EFF6FF;color:#1D4ED8;">共 4,562 分子</span>
      </div>
      <div class="bar-group">
        <div class="bar-item">
          <div class="bar-label-row"><span style="color:#047857;">A 类：主力原版模型 (完整特征)</span><span style="color:#047857;">165 个</span></div>
          <div class="bar-track"><div class="bar-fill" style="width:14%; background:#059669;">165</div></div>
        </div>
        <div class="bar-item">
          <div class="bar-label-row"><span style="color:#1D4ED8;">B 类：主力正式版匹配回填</span><span style="color:#1D4ED8;">795 个</span></div>
          <div class="bar-track"><div class="bar-fill" style="width:30%; background:#2563EB;">795</div></div>
        </div>
        <div class="bar-item">
          <div class="bar-label-row"><span style="color:#B45309;">C 类：HERB 结构模型外推（标明参考）</span><span style="color:#B45309;">3,602 个</span></div>
          <div class="bar-track"><div class="bar-fill" style="width:82%; background:#D97706;">3,602</div></div>
        </div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-title">
        <span>2. 消融实验：为什么 C 类改用结构兜底模型？</span>
        <span class="badge-pill" style="background:#FEF2F2;color:#DC2626;">实测误差减半</span>
      </div>
      <table class="clean-table">
        <thead>
          <tr>
            <th>外推方案对比</th>
            <th>平均偏差 (MAE)</th>
            <th>分类表现</th>
            <th>结论</th>
          </tr>
        </thead>
        <tbody>
          <tr class="warn">
            <td>缺维强跑主模型</td>
            <td><b>0.290（偏差大）</b></td>
            <td>翻转率 44.4%</td>
            <td><b>弃用 ✗</b></td>
          </tr>
          <tr class="hl">
            <td>切换结构兜底模型</td>
            <td><b>0.135（误差减半）</b></td>
            <td>一致率 79.0%</td>
            <td><b>采用 ✓</b></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<!-- 图 4：跨算法族交叉验证 (Slide 06) - 极简防挑刺版 -->
<div id="chart-cross-validation" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag purple">CROSS-VALIDATION</span>
    跨算法族独立验证与双模型一致性分析
  </div>
  <div class="two-col">
    <div class="panel">
      <div class="panel-title">
        <span>1. 四种不同算法族测试集表现</span>
        <span class="badge-pill" style="background:#F5F3FF;color:#6D28D9;">判别信号稳健</span>
      </div>
      <table class="clean-table">
        <thead>
          <tr>
            <th>模型名称</th>
            <th>算法族</th>
            <th>ROC-AUC</th>
            <th>PR-AUC</th>
          </tr>
        </thead>
        <tbody>
          <tr class="hl">
            <td><b>主模型 (PU-RF)</b></td>
            <td>PU 集成树</td>
            <td><b>0.903 ± 0.008</b></td>
            <td><b>0.573</b></td>
          </tr>
          <tr class="hl">
            <td><b>独立 XGBoost</b></td>
            <td>梯度提升树</td>
            <td><b>0.896 ± 0.006</b></td>
            <td><b>0.562</b></td>
          </tr>
          <tr>
            <td>独立 MLP</td>
            <td>神经网络</td>
            <td>0.853 ± 0.022</td>
            <td>0.535</td>
          </tr>
          <tr>
            <td>独立逻辑回归</td>
            <td>线性基线</td>
            <td>0.823 ± 0.011</td>
            <td>0.474</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="panel">
      <div class="panel-title">
        <span>2. 双模型一致性与分歧来源</span>
        <span class="badge-pill" style="background:#ECFDF5;color:#047857;">一致率 73.9%</span>
      </div>
      <div class="bar-group">
        <div class="bar-item">
          <div class="bar-label-row"><span>两套算法分类结论一致</span><span style="color:#047857;">122 / 165 (73.9%)</span></div>
          <div class="bar-track"><div class="bar-fill" style="width:73.9%; background:#059669;">73.9% 结论一致</div></div>
        </div>
        <div class="bar-item">
          <div class="bar-label-row"><span>分歧主要集中于：大分子 (MW&gt;400) 与糖苷类</span><span style="color:#B45309;">如落新妇苷、皂苷类</span></div>
          <div class="bar-track"><div class="bar-fill" style="width:65%; background:#D97706;">PU 协议对未标注苷类更宽容</div></div>
        </div>
      </div>
      <div style="margin-top:16px; padding:12px 16px; background:#FFFBEB; border-radius:10px; font-size:14px; color:#78350F; font-weight:600; line-height:1.5;">
        ● 原因：主模型采用 PU 采样，包容未标注的苷类代谢物；独立模型采用标准二分类，对未标注大分子偏保守。
      </div>
    </div>
  </div>
</div>

<!-- 图 5：留一法适用域与可信度四件套 (Slide 07) - 极简版 -->
<div id="chart-ad-distribution" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag">CREDIBILITY QUARTET</span>
    留一法 (LOO) 适用域量化与「可信度四件套」
  </div>
  <div class="two-col">
    <div class="panel">
      <div class="panel-title">
        <span>1. 训练集 Tanimoto 结构相似度分位标定</span>
        <span class="badge-pill" style="background:#ECFDF5;color:#047857;">主动亮出边界</span>
      </div>
      <div class="bar-group">
        <div class="bar-item">
          <div class="bar-label-row"><span>A 类 165 核心成分</span><span>域内 160 · 边缘 2 · 域外 3</span></div>
          <div class="bar-track">
            <div class="bar-fill" style="width:92%; background:#059669;">域内 160 (97%)</div>
            <div class="bar-fill" style="width:4%; background:#D97706;"></div>
            <div class="bar-fill" style="width:4%; background:#DC2626;"></div>
          </div>
        </div>
        <div class="bar-item">
          <div class="bar-label-row"><span>全库 4,558 分子分布</span><span>域内 2,775 · 边缘 1,193 · 域外 590</span></div>
          <div class="bar-track">
            <div class="bar-fill" style="width:60.9%; background:#059669;">域内 60.9%</div>
            <div class="bar-fill" style="width:26.2%; background:#D97706;">边缘 26.2%</div>
            <div class="bar-fill" style="width:12.9%; background:#DC2626;">12.9%</div>
          </div>
        </div>
      </div>
      <div style="margin-top:16px; padding:12px 16px; background:#FEF2F2; border-radius:10px; font-size:14px; color:#991B1B; font-weight:700;">
        ● 相似度 ≤ 0.333 判为「应用域外」，界面直接亮红牌提示“预测可靠性有限”。
      </div>
    </div>
    <div class="panel">
      <div class="panel-title">
        <span>2. 科学可信度四件套闭环</span>
        <span class="badge-pill" style="background:#EFF6FF;color:#1D4ED8;">四大透明保障</span>
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
        <div class="arch-card highlight"><b>① 适用域红牌预警</b><span>留一法量化模型能力边界</span></div>
        <div class="arch-card tech"><b>② ChEMBL 实验活性</b><span>465 条体外实测 Ki/IC50</span></div>
        <div class="arch-card" style="background:#FAF5FF; border-color:#D8B4FE;"><b style="color:#6D28D9;">③ 跨算法交叉互验</b><span>4 种算法族双向印证</span></div>
        <div class="arch-card amber"><b>④ 三档暴露量区间</b><span>保守/基准/乐观诚实区间</span></div>
      </div>
    </div>
  </div>
</div>

<!-- 图 6：UMAP 化学空间散点图 (Slide 08) - 极简版 -->
<div id="chart-umap-manifold" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag blue">CHEMICAL SPACE</span>
    全库 4,558 分子 UMAP 化学空间二维拓扑投影
  </div>
  <div class="two-col" style="grid-template-columns: 1.4fr 0.6fr;">
    <div class="panel" style="display:flex; flex-direction:column; align-items:center; padding:16px;">
      <canvas id="umap-canvas" width="800" height="400" style="border:1px solid #E2E8F0; border-radius:12px; background:#FAF8F5;"></canvas>
      <div style="display:flex; gap:20px; margin-top:12px; font-size:13.5px; font-weight:800; color:#334155;">
        <span><i style="display:inline-block;width:11px;height:11px;border-radius:50%;background:#059669;margin-right:5px;"></i>主力高入血 (≥0.7)</span>
        <span><i style="display:inline-block;width:11px;height:11px;border-radius:50%;background:#D97706;margin-right:5px;"></i>主力中等</span>
        <span><i style="display:inline-block;width:11px;height:11px;border-radius:50%;background:#DC2626;margin-right:5px;"></i>主力偏低</span>
        <span><i style="display:inline-block;width:11px;height:11px;border-radius:50%;background:#C2A878;margin-right:5px;"></i>C类外推 (3,598)</span>
      </div>
    </div>
    <div class="panel" style="display:flex; flex-direction:column; justify-content:center; gap:18px;">
      <div class="arch-card highlight" style="text-align:left; padding:16px;">
        <b>● 骨架自然聚类</b>
        <span>1024 维指纹降维后，黄酮、皂苷、单萜自发形成空间岛礁。</span>
      </div>
      <div class="arch-card tech" style="text-align:left; padding:16px;">
        <b>● 高入血分子局部富集</b>
        <span>绿色高入血成分沿特定分子骨架聚集，验证拓扑特征有效性。</span>
      </div>
      <div class="arch-card amber" style="text-align:left; padding:16px;">
        <b>● 三种视图实时切换</b>
        <span>支持按「入血概率 / 应用域 / 模型一致性」一键切换染色。</span>
      </div>
    </div>
  </div>
</div>

<!-- 图 7：ChEMBL 实验活性与三维指数 (Slide 09) - 极简版 -->
<div id="chart-target-3d-index" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag">MECHANISM &amp; EVALUATION</span>
    ChEMBL 实验活性锚定与「食养科学三维评价指数」
  </div>
  <div class="two-col">
    <div class="panel">
      <div class="panel-title">
        <span>1. 欧洲 ChEMBL 数据库体外实测背书</span>
        <span class="badge-pill" style="background:#EFF6FF;color:#1D4ED8;">实验证据挂链</span>
      </div>
      <div class="bar-group">
        <div class="bar-item">
          <div class="bar-label-row"><span>结构精确匹配命中</span><span style="color:#1D4ED8;">126 / 165 (76.4%)</span></div>
          <div class="bar-track"><div class="bar-fill" style="width:76.4%; background:#2563EB;">126 个成分命中</div></div>
        </div>
        <div class="bar-item">
          <div class="bar-label-row"><span>人类蛋白靶点实测活性入库</span><span style="color:#047857;">465 条 Ki / IC50</span></div>
          <div class="bar-track"><div class="bar-fill" style="width:65%; background:#059669;">465 条实测记录</div></div>
        </div>
        <div class="bar-item">
          <div class="bar-label-row"><span>L1 级强实验证据 (Ki/IC50 ≤ 1 μM)</span><span style="color:#B45309;">127 条强证据</span></div>
          <div class="bar-track"><div class="bar-fill" style="width:45%; background:#D97706;">127 条 L1 强证据</div></div>
        </div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-title">
        <span>2. 食养科学三维评价指数（覆盖全库 73 方）</span>
        <span class="badge-pill" style="background:#ECFDF5;color:#047857;">百分制客观评分</span>
      </div>
      <div style="display:flex; flex-direction:column; gap:12px;">
        <div class="arch-card highlight" style="text-align:left; padding:14px 18px;">
          <b>维度一：入血潜力 (Absorption)</b>
          <span>方剂核心活性成分 PU-Learning 入血概率均值映射。</span>
        </div>
        <div class="arch-card tech" style="text-align:left; padding:14px 18px;">
          <b>维度二：多靶协同 (Synergy)</b>
          <span>基于 10,154 个人类蛋白靶点网络的调控连接度评估。</span>
        </div>
        <div class="arch-card amber" style="text-align:left; padding:14px 18px;">
          <b>维度三：证据强度 (Evidence)</b>
          <span>综合卫健委名录/古籍出处 (A级) 与实验文献 (B级) 分级加权。</span>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- 图 8：业务决策流 (Slide 13) - 极简版 -->
<div id="chart-pantry-recommendation" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag">WORKFLOW</span>
    端侧识方、茶罐反向配伍与体质安全推荐闭环
  </div>
  <div class="flow-row">
    <div class="flow-step step-blue">
      <div>
        <div class="step-num" style="color:#1D4ED8;">01 · 端侧识方</div>
        <div class="step-title">本地 RapidOCR</div>
        <div class="step-list">
          • 纯 CPU 离线秒级识别<br>
          • 零云端 API 调用成本<br>
          • 劣化模糊图 100% 召回
        </div>
      </div>
      <div class="step-badge" style="background:#DBEAFE;color:#1E40AF;">1.5s ~ 3.6s 极速</div>
    </div>
    <div class="flow-arrow">→</div>
    <div class="flow-step step-purple">
      <div>
        <div class="step-num" style="color:#6D28D9;">02 · 拓扑纠偏</div>
        <div class="step-title">本草形近字纠错</div>
        <div class="step-list">
          • 金银化 → 金银花<br>
          • 枸札 → 枸杞子<br>
          • 阵皮 → 陈皮
        </div>
      </div>
      <div class="step-badge" style="background:#F3E8FF;color:#6B21A8;">纠错 11/12 · 误纠 0/40</div>
    </div>
    <div class="flow-arrow">→</div>
    <div class="flow-step step-green">
      <div>
        <div class="step-num" style="color:#047857;">03 · 反向组方</div>
        <div class="step-title">茶罐子集图覆盖</div>
        <div class="step-list">
          • 勾选现有三五味食材<br>
          • 直接能煮优先排序<br>
          • 差一味可凑智能提示
        </div>
      </div>
      <div class="step-badge" style="background:#DCFCE7;color:#166534;">五大分类货架</div>
    </div>
    <div class="flow-arrow">→</div>
    <div class="flow-step step-amber">
      <div>
        <div class="step-num" style="color:#B45309;">04 · 个性推荐</div>
        <div class="step-title">安全剪枝 + 协同</div>
        <div class="step-list">
          • CCMQ 67 题国标量表<br>
          • 孕哺/体质相冲一票否决<br>
          • 24 节气与入血丰度加权
        </div>
      </div>
      <div class="step-badge" style="background:#FEF3C7;color:#92400E;">安全红线第一</div>
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
  const pad = 26;
  const W = canvas.width - pad * 2;
  const H = canvas.height - pad * 2;

  ctx.strokeStyle = '#E2E8F0';
  ctx.lineWidth = 1;
  for (let i = 1; i < 5; i++) {{
    ctx.beginPath(); ctx.moveTo(pad, pad + (H * i) / 5); ctx.lineTo(pad + W, pad + (H * i) / 5); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(pad + (W * i) / 5, pad); ctx.lineTo(pad + (W * i) / 5, pad + H); ctx.stroke();
  }}

  const colorMap = {{
    ext: 'rgba(194, 168, 120, 0.45)',
    low: 'rgba(220, 38, 38, 0.82)',
    mid: 'rgba(217, 119, 6, 0.85)',
    high: 'rgba(5, 150, 105, 0.92)'
  }};
  for (const layer of ['ext', 'low', 'mid', 'high']) {{
    ctx.fillStyle = colorMap[layer];
    const r = layer === 'ext' ? 2.8 : 4.5;
    for (const [x, y, cat] of pts) {{
      if (cat !== layer) continue;
      const cx = pad + ((x - minX) / (maxX - minX)) * W;
      const cy = pad + H - ((y - minY) / (maxY - minY)) * H;
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
    }}
  }}
</script>
</body>
</html>
"""


async def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pts = load_umap_points()
    html_file = OUT_DIR / "temp_diagrams.html"
    html_file.write_text(build_html(json.dumps(pts)), encoding="utf-8")

    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME)
        ctx = await browser.new_context(viewport={"width": 1480, "height": 5000}, device_scale_factor=2)
        page = await ctx.new_page()
        await page.goto(f"file:///{html_file.as_posix()}", wait_until="networkidle")
        await page.wait_for_timeout(500)

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
            el = await page.query_selector(selector)
            if el:
                await el.screenshot(path=str(OUT_DIR / filename))
                print(f"Exported minimalist {filename}")
        await browser.close()

    if html_file.exists():
        html_file.unlink()


if __name__ == "__main__":
    asyncio.run(main())
