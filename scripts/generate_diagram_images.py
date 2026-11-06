# -*- coding: utf-8 -*-
"""
生成答辩专用的白底学术风、高分辨率架构图与算法流程图 PNG 图片
使用 Playwright 以 2x 设备像素比高清渲染
产物输出至 docs/diagrams/
"""
import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "diagrams"
CHROME = r"C:\Users\zzx05\AppData\Local\ms-playwright\chromium-1248\chrome-win64\chrome.exe"

# 4 个图表的 HTML 模板（浅色学术科技风：纯白背景、柔和卡片、石墨黑文字、本草绿与科技蓝主色）
HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif; }
  body { background: #FFFFFF; color: #1E293B; display: flex; flex-direction: column; gap: 40px; padding: 40px; width: 1400px; }
  .diagram-container { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 32px; box-shadow: 0 4px 20px rgba(0,0,0,0.04); position: relative; }
  .diagram-title { font-size: 24px; font-weight: 700; color: #0F172A; margin-bottom: 6px; display: flex; align-items: center; gap: 10px; }
  .diagram-tag { font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 20px; background: #ECFDF5; color: #059669; border: 1px solid #A7F3D0; }
  .diagram-desc { font-size: 14px; color: #64748B; margin-bottom: 24px; }
  
  /* 架构图分层 */
  .arch-grid { display: flex; flex-direction: column; gap: 14px; }
  .arch-row { display: flex; border: 1px solid #E2E8F0; border-radius: 12px; overflow: hidden; background: #F8FAFC; }
  .arch-header { width: 180px; padding: 18px 16px; font-weight: 700; font-size: 15px; display: flex; align-items: center; justify-content: center; text-align: center; color: #FFFFFF; flex-shrink: 0; }
  .arch-body { flex: 1; padding: 14px 20px; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; background: #FFFFFF; }
  .arch-card { border: 1px solid #CBD5E1; border-radius: 8px; padding: 10px 14px; font-size: 13px; font-weight: 500; background: #F8FAFC; color: #334155; }
  .arch-card b { color: #0F172A; font-weight: 600; display: block; margin-bottom: 2px; }
  .arch-card.highlight { background: #F0FDF4; border-color: #86EFAC; color: #166534; }
  .arch-card.highlight b { color: #15803D; }
  .arch-card.tech { background: #EFF6FF; border-color: #93C5FD; color: #1E40AF; }
  .arch-card.tech b { color: #1D4ED8; }
  .arch-card.amber { background: #FFFBEB; border-color: #FDE68A; color: #92400E; }
  .arch-card.amber b { color: #B45309; }
  
  /* 流程图节点与箭头 */
  .flow-row { display: flex; align-items: stretch; justify-content: space-between; gap: 16px; margin-top: 10px; }
  .flow-step { flex: 1; border: 1px solid #CBD5E1; border-radius: 12px; padding: 18px; background: #F8FAFC; display: flex; flex-direction: column; position: relative; }
  .flow-step.step-green { background: #F0FDF4; border-color: #86EFAC; }
  .flow-step.step-blue { background: #EFF6FF; border-color: #93C5FD; }
  .flow-step.step-amber { background: #FFFBEB; border-color: #FDE68A; }
  .flow-step.step-purple { background: #FAF5FF; border-color: #E9D5FF; }
  .step-num { font-size: 11px; font-weight: 700; text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.5px; }
  .step-title { font-size: 16px; font-weight: 700; color: #0F172A; margin-bottom: 8px; }
  .step-content { font-size: 12.5px; color: #475569; line-height: 1.5; }
  .step-badge { display: inline-block; margin-top: 10px; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 4px; }
  
  .flow-arrow { display: flex; align-items: center; justify-content: center; color: #94A3B8; font-size: 22px; font-weight: bold; }
  
  /* 消融对比表格 */
  .comp-table { width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 13px; }
  .comp-table th, .comp-table td { border: 1px solid #E2E8F0; padding: 10px 14px; text-align: left; }
  .comp-table th { background: #F1F5F9; color: #334155; font-weight: 600; }
  .comp-table td { background: #FFFFFF; color: #475569; }
  .comp-table tr.hl td { background: #F0FDF4; font-weight: 600; color: #166534; }
  .comp-table tr.warn td { background: #FEF2F2; color: #991B1B; }
</style>
</head>
<body>

<!-- 图 1：系统全栈技术分层架构图 -->
<div id="chart-system-arch" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag">架构全景</span>
    《食养有据》全栈技术与算法总体架构图
  </div>
  <div class="diagram-desc">基于中药多组学与 PU-Learning 机器学习的五层端到端科学体系（学术白底设计）</div>
  
  <div class="arch-grid">
    <!-- 第五层 -->
    <div class="arch-row">
      <div class="arch-header" style="background: #2563EB;">五、工程与交互层<br><small style="font-size:11px;opacity:0.8;">Client & Accessibility</small></div>
      <div class="arch-body">
        <div class="arch-card tech"><b>FastAPI 异步微秒级推断</b>57 路径 / 61 端点 · 响应延迟 < 15ms</div>
        <div class="arch-card tech"><b>双 SQLite 动静物理隔离</b>只读科研库 shiyang.db ＋ WAL 读写库 user.db</div>
        <div class="arch-card highlight"><b>长辈高对比大字适老模式</b>自研 FontScale 动态字号缩放 · 消除银发数字鸿沟</div>
        <div class="arch-card"><b>Vue3 ＋ Vant 移动优先界面</b>全站纯矢量线性 SVG 图标 · 严谨学术风</div>
      </div>
    </div>
    
    <!-- 第四层 -->
    <div class="arch-row">
      <div class="arch-header" style="background: #059669;">四、协同决策层<br><small style="font-size:11px;opacity:0.8;">Decision & Services</small></div>
      <div class="arch-body">
        <div class="arch-card highlight"><b>【我的茶罐】反向配伍引擎</b>105 味全分类货架 · 食材子集图覆盖贪心排序</div>
        <div class="arch-card highlight"><b>【对比实验室】同屏 PK</b>多方活性成分重合度 ＋ 三维机制雷达同屏叠加</div>
        <div class="arch-card"><b>CCMQ 67 题国标体质判定</b>9 种体质标准转化分与主导偏颇判定</div>
        <div class="arch-card amber"><b>安全禁忌剪枝引擎 (Safety Gate)</b>体质相冲忌口 ＋ 孕妇/儿童/慢病特殊人群硬拦截</div>
        <div class="arch-card"><b>24 节气当令协同因数</b>时令食养主题加成 ＋ 用户打卡收藏隐式反馈</div>
      </div>
    </div>
    
    <!-- 第三层 -->
    <div class="arch-row">
      <div class="arch-header" style="background: #D97706;">三、核心算法矩阵<br><small style="font-size:11px;opacity:0.8;">Core Algorithms</small></div>
      <div class="arch-body">
        <div class="arch-card highlight"><b>PU-Learning 入血预测模型</b>PU-Bagging ＋ RandomForest · ROC-AUC 0.903</div>
        <div class="arch-card amber"><b>prob_caliber 多口径分层治理</b>A/B/C 三级口径隔离 · 拒绝特征退化强行外推</div>
        <div class="arch-card"><b>留一法 (LOO) 全库适用域量化</b>4,558 分子覆盖 · 域内 2,775 / 边缘 1,193 / 域外 590</div>
        <div class="arch-card tech"><b>全库 UMAP 高维流形降维</b>1024D → 2D · 入血概率与模型一致性三色拓扑流形</div>
        <div class="arch-card highlight"><b>本地 RapidOCR ＋ 形近字拓扑纠错</b>纯 CPU 毫秒级断网运行 · 纠错率 11/12 · 误纠率 0/40</div>
        <div class="arch-card"><b>超几何检验靶点通路富集</b>映射抗炎、抗氧化、免疫调节三维生物活性机制</div>
        <div class="arch-card"><b>三档情景转移率暴露量估算</b>保守 0.3 / 基准 0.5 / 乐观 0.7 · 拒绝伪精度</div>
      </div>
    </div>
    
    <!-- 第二层 -->
    <div class="arch-row">
      <div class="arch-header" style="background: #0891B2;">二、特征工程层<br><small style="font-size:11px;opacity:0.8;">Feature Engineering</small></div>
      <div class="arch-body">
        <div class="arch-card"><b>SMILES 化学规范化解析</b>基于 RDKit 统一分子标准化结构表达</div>
        <div class="arch-card tech"><b>1024-bit Morgan 拓扑指纹</b>ECFP4 (Radius=2) 提取微观分子亚结构图特征</div>
        <div class="arch-card"><b>理化常数全库补全</b>全库 4,558 分子计算 MW、LogP、TPSA、Lipinski 解读</div>
        <div class="arch-card"><b>端侧视觉特征提取</b>自适应灰度二值化 ＋ 逐行置信度剪枝过滤</div>
      </div>
    </div>
    
    <!-- 第一层 -->
    <div class="arch-row">
      <div class="arch-header" style="background: #475569;">一、数据底座层<br><small style="font-size:11px;opacity:0.8;">Data Foundation</small></div>
      <div class="arch-body">
        <div class="arch-card highlight"><b>卫健委药食同源全目录</b>105 味药材 100% 覆盖（四批名录全收录）</div>
        <div class="arch-card"><b>ccTCM 2.0 权威科研库</b>6,196 行含量区间 ＋ 40,634 条靶点关联（赵玉男团队）</div>
        <div class="arch-card tech"><b>ChEMBL 国际实验数据库</b>126 个成分匹配 · 465 条体外实测 Ki/IC50 · 127 条 L1 强证据</div>
        <div class="arch-card"><b>中药多组学知识网络</b>SymMap 703 味性味归经 ＋ UniProt 10,154 靶点 ＋ 6.2万互作</div>
      </div>
    </div>
  </div>
</div>

<!-- 图 2：PU-Learning 与多口径消融算法流程图 -->
<div id="chart-algo-pulearning" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag">核心算法</span>
    PU-Learning 入血预测模型与消融分层治理流程
  </div>
  <div class="diagram-desc">针对无真实负样本特性创新集成协议，通过消融实验严谨隔离外推口径，杜绝伪精度</div>
  
  <div class="flow-row">
    <div class="flow-step step-blue">
      <div class="step-num" style="color:#2563EB;">STEP 1 · 样本构建</div>
      <div class="step-title">正样本与未标注池</div>
      <div class="step-content">
        <b>正样本集 P (282个)</b>：文献明确报道在血中检出的移行分子 (Label=1)<br><br>
        <b>未标注集 U (1,887个)</b>：全量中药候选化合物分子，正负混合未知<br><br>
        <b>提取特征</b>：1024-bit Morgan 拓扑指纹 ＋ 7 维理化描述符
      </div>
      <div class="step-badge" style="background:#DBEAFE;color:#1E40AF;">样本不平衡 1:7</div>
    </div>
    
    <div class="flow-arrow">➔</div>
    
    <div class="flow-step step-green">
      <div class="step-num" style="color:#059669;">STEP 2 · PU-Bagging</div>
      <div class="step-title">集成学习迭代抽样</div>
      <div class="step-content">
        <b>K 轮均衡重采样</b>：每轮保持全部正例 P，从 U 中随机均匀采样等量伪负例 U_k<br><br>
        <b>基学习器训练</b>：训练多棵独立随机森林树 (RandomForest)<br><br>
        <b>软投票集成</b>：多轮后验概率均值软投票，消解未标注样本中的噪声污染
      </div>
      <div class="step-badge" style="background:#DCFCE7;color:#166534;">ROC-AUC 0.903</div>
    </div>
    
    <div class="flow-arrow">➔</div>
    
    <div class="flow-step step-purple">
      <div class="step-num" style="color:#7C3AED;">STEP 3 · 跨范式互验</div>
      <div class="step-title">3 算法族独立对照</div>
      <div class="step-content">
        <b>独立 XGBoost</b>: AUC 0.8961 (提升树)<br>
        <b>独立 MLP</b>: AUC 0.8529 (神经网络)<br>
        <b>独立逻辑回归</b>: AUC 0.8225 (线性)<br><br>
        <b>一致率 73.3%</b>：44 个分歧点 100% 聚拢于皂苷类，由二分类惩罚与 PU 降权协议差异引起，生物学完全自洽！
      </div>
      <div class="step-badge" style="background:#F3E8FF;color:#6B21A8;">信号深植于分子拓扑</div>
    </div>
    
    <div class="flow-arrow">➔</div>
    
    <div class="flow-step step-amber">
      <div class="step-num" style="color:#D97706;">STEP 4 · 消融治理</div>
      <div class="step-title">三级口径严格隔离</div>
      <div class="step-content">
        <b>A 类老主力 (165个)</b>: 完整 ADME<br>
        <b>B 类官方回填 (795个)</b>: SMILES 精确匹配<br>
        <b>C 类扩容外推 (3,602个)</b>: HERB 兜底模型<br><br>
        <b>严禁强行外推</b>：消融实验证明 ccTCM 缺特征偏差高达 0.29（抛硬币），HERB 偏差仅 0.135。前端诚实标明外推，绝不填 0！
      </div>
      <div class="step-badge" style="background:#FEF3C7;color:#92400E;">prob_caliber 治理</div>
    </div>
  </div>
</div>

<!-- 图 3：科学可信度四件套闭环机制图 -->
<div id="chart-credibility-quartet" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag">可信度工程</span>
    科学可信度四件套闭环机理图 (Credibility Quartet)
  </div>
  <div class="diagram-desc">“可信的本质不是每个数字都完美，而是每个数字都诚实”——全链条透明防黑盒</div>
  
  <div class="flow-row">
    <!-- Pillar 1 -->
    <div class="flow-step step-green">
      <div class="step-num" style="color:#059669;">PILLAR 1 · 适用域量化</div>
      <div class="step-title">留一法 (LOO) 标定</div>
      <div class="step-content">
        ● <b>Morgan 指纹 Tanimoto 距离</b>：度量化合物与 2,437 训练集最大相似度<br><br>
        ● <b>留一法分位临界截断</b>：<br>
        • ≤ 0.333 (5%分位) → <b>应用域外</b><br>
        • ≤ 0.582 (25%分位) → <b>应用域边缘</b><br>
        • > 0.582 → <b>应用域内 (高置信)</b><br><br>
        ● <b>全库 4,558 实测</b>：域内 2,775 / 边缘 1,193 / 域外 590。域外成分前台亮红灯预警！
      </div>
    </div>
    
    <!-- Pillar 2 -->
    <div class="flow-step step-blue">
      <div class="step-num" style="color:#2563EB;">PILLAR 2 · 实验实测</div>
      <div class="step-title">ChEMBL 权威背书</div>
      <div class="step-content">
        ● <b>补齐体外实验关键证据环</b>：<br>
        对接欧洲生物信息研究所数据库<br><br>
        ● <b>实测数据覆盖</b>：<br>
        • 126 个成分结构精确匹配<br>
        • 73 个成分入库 465 条实验活性<br>
        • 127 条 L1 强证据 (Ki/IC50 ≤ 1μM)<br><br>
        ● <b>严肃学术边界</b>：<br>
        明确标注“体外活性 ≠ 人体功效”。
      </div>
    </div>
    
    <!-- Pillar 3 -->
    <div class="flow-step step-purple">
      <div class="step-num" style="color:#7C3AED;">PILLAR 3 · 交叉互验</div>
      <div class="step-title">跨算法范式校准</div>
      <div class="step-content">
        ● <b>排除特定算法偏倚</b>：<br>
        主模型 PU-Bagging 与独立提升树 XGBoost 双向校准验证<br><br>
        ● <b>全透明一致性徽章</b>：<br>
        • 一致高（双模型共识高置信）<br>
        • 一致低（双模型共识低置信）<br>
        • 主模型单独高（解构皂苷分歧）<br><br>
        ● <b>分歧可解释</b>：分歧反向印证算法对中药菌群代谢的深刻洞察。
      </div>
    </div>
    
    <!-- Pillar 4 -->
    <div class="flow-step step-amber">
      <div class="step-num" style="color:#D97706;">PILLAR 4 · 情景估算</div>
      <div class="step-title">三档转移率模拟</div>
      <div class="step-content">
        ● <b>定量药理学 Fit-for-Purpose</b>：<br>
        不具备实测清除率参数时，强建 PBPK 属于参数伪造！<br><br>
        ● <b>煎煮三档情景区间</b>：<br>
        • 保守情景 (η = 0.3)<br>
        • 基准情景 (η = 0.5)<br>
        • 乐观情景 (η = 0.7)<br><br>
        ● <b>输出真实区间</b>：<br>
        呈现诚实摄入区间 [min, max] mg。
      </div>
    </div>
  </div>
</div>

<!-- 图 4：茶罐反向配伍与多目标推荐功能业务流图 -->
<div id="chart-pantry-recommendation" class="diagram-container">
  <div class="diagram-title">
    <span class="diagram-tag">业务流与决策</span>
    端侧识方、茶罐反向图配伍与个性化推荐决策流
  </div>
  <div class="diagram-desc">打通“拍照识方 → 拓扑纠偏 → 105 味茶罐反向组方 → CCMQ 体质协同推荐”的完整用户决策闭环</div>
  
  <div class="flow-row">
    <div class="flow-step step-blue">
      <div class="step-num" style="color:#2563EB;">INPUT & OCR</div>
      <div class="step-title">拍照与文本识方</div>
      <div class="step-content">
        <b>本地 RapidOCR (ONNX)</b><br>
        • 纯 CPU 毫秒级断网识别<br>
        • 极端模糊/光照不均 100% 正确<br>
        • 丢弃 Conf < 0.5 低质行<br><br>
        <b>或手动勾选 105 味茶罐</b>：<br>
        勾选手边现有的三五味食材
      </div>
    </div>
    
    <div class="flow-arrow">➔</div>
    
    <div class="flow-step step-purple">
      <div class="step-num" style="color:#7C3AED;">AI REPAIR</div>
      <div class="step-title">本草形近字纠偏</div>
      <div class="step-content">
        <b>拓扑纠错 correct_herb_name</b><br>
        • 105 药食同源 ＋ 703 SymMap 词表<br>
        • 同长度形近替换 (金银化→金银花)<br>
        • 受限省字匹配 (枸札→枸杞子)<br>
        • 编辑距离 1 匹配 (阵皮→陈皮)<br><br>
        <b>实测</b>：纠错率 11/12 · 误纠率 0/40
      </div>
    </div>
    
    <div class="flow-arrow">➔</div>
    
    <div class="flow-step step-green">
      <div class="step-num" style="color:#059669;">INVERSE MATCH</div>
      <div class="step-title">茶罐反向图覆盖</div>
      <div class="step-content">
        <b>食材子集图匹配</b><br>
        Coverage = 命中必需料 / 方子必需料<br><br>
        <b>多维决策矩阵排序</b>：<br>
        ① 覆盖率降序 (直接可煮优先)<br>
        ② 缺失食材数升序 (缺一料好凑)<br>
        ③ 高入血活性成分数降序
      </div>
    </div>
    
    <div class="flow-arrow">➔</div>
    
    <div class="flow-step step-amber">
      <div class="step-num" style="color:#D97706;">MULTI-TARGET REC</div>
      <div class="step-title">CCMQ 多目标协同</div>
      <div class="step-content">
        <b>第一道安全剪枝防线</b>：<br>
        体质相冲忌口 ＋ 孕期等禁忌一票否决<br><br>
        <b>四维协同加权打分</b>：<br>
        S = w1·体质适宜 ＋ w2·24节气时令 ＋ w3·行为偏好 ＋ w4·高入血丰度<br><br>
        <b>输出</b>：个性化推荐 ＋ 通俗解读
      </div>
    </div>
  </div>
</div>

</body>
</html>
"""

async def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html_file = OUT_DIR / "temp_diagrams.html"
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(HTML_PAGE)
    
    print(f"临时 HTML 文件已就绪: {html_file}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME)
        # 视口宽度 1480，device_scale_factor=2 保证 Retina 级极高清晰度
        ctx = await browser.new_context(viewport={"width": 1480, "height": 3600}, device_scale_factor=2)
        page = await ctx.new_page()
        await page.goto(f"file:///{html_file.as_posix()}", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        
        diagrams = [
            ("diagram_system_architecture.png", "#chart-system-arch"),
            ("diagram_algorithm_pulearning.png", "#chart-algo-pulearning"),
            ("diagram_credibility_quartet.png", "#chart-credibility-quartet"),
            ("diagram_pantry_recommendation.png", "#chart-pantry-recommendation"),
        ]
        
        for filename, selector in diagrams:
            element = await page.query_selector(selector)
            if element:
                target_path = OUT_DIR / filename
                await element.screenshot(path=str(target_path))
                print(f"成功高清导出: {target_path} (Retina 2x)")
            else:
                print(f"未找到元素: {selector}")
                
        await browser.close()
    
    # 清理临时 HTML
    if html_file.exists():
        html_file.unlink()
    print("\n所有 4 张白底高清架构与流程图生成完毕！")

if __name__ == "__main__":
    asyncio.run(main())
