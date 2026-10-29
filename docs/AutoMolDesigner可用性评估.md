# AutoMolDesigner 可用性评估（2026-10-30 实测）

> 目的：判断这个老师提供的软件能否真正用于「食养有据」的可信度建设。
> 所有结论均来自本机实测，非推测。

## 一、结论先说

| 问题 | 结论 |
|---|---|
| 能启动吗 | ✅ **能**。双击 `program/AutoMolDesigner-GUI.exe` 正常启动，进程占约 324MB 内存，无报错 |
| 能脚本化 / 接进后端吗 | ❌ **不能**。PyInstaller 打包的纯 GUI 程序，无 CLI 参数（exe 内不含 `--smiles` 等入参；`--help` 直接弹窗） |
| 数据集能用吗 | ✅ **能**，且价值最大（见第三节） |
| 预训练模型能用吗 | ⚠️ 能用但**与本项目无关**（ChEMBL 化学语言模型，用于分子生成） |
| 建议怎么用 | **只用它的数据集 + 借鉴它的 AutoML 方法论，用本地 sklearn/xgboost 复现**，不集成 exe |

## 二、实测细节

### 2.1 启动测试
```
program/AutoMolDesigner-GUI.exe
→ 进程 AutoMolDesigner-GUI.exe PID 34668，内存 324,072 K
→ stdout/stderr 无任何报错
```
环境依赖已全部打包（PySide6 / rdkit / numpy / pandas / sklearn / xgboost / lightgbm / catboost / ray / torch），确实"环境都挺好"。

### 2.2 为什么不能脚本化
- 是 PyInstaller onefile 打包的 Qt 桌面程序
- exe 内字符串扫描：`--smiles` 出现 0 次，`argparse` 仅 1 次（框架级残留）
- `AutoMolDesigner-GUI.exe --help` 不打印帮助，直接启动 GUI 窗口
- 结论：**只能人工在界面上点，无法批处理、无法接 API**

### 2.3 目录结构
```
AutoMolDesigner-GUI/
├── program/              # PyInstaller 打包体（39MB exe + 依赖）
└── working_dir/
    ├── datasets/         # ★ 真正的价值所在
    └── projects/
        ├── ChEMBL32-pretrain-linux/   # 化学语言模型预训练（5.7MB pkl）
        ├── Ecoli-finetune-win/        # 大肠杆菌活性微调
        └── Saureus-finetune-win/      # 金黄色葡萄球菌活性微调
```

## 三、数据集清单（实测规模）

| 文件 | 规模 | 内容 | 对食养有据的用处 |
|---|---|---|---|
| `PPB_full.xlsx` | **3,921 × 2** | SMILES + 血浆蛋白结合 label | ⭐ 暴露量链缺的一环：入血≠游离 |
| `PPB_train/test.xlsx` | 3,528 / 393 | 同上已切分 | 可直接用于训练/验证 |
| `Tox_full.xlsx` | **9,668 × 2** | SMILES + 毒性 label | 安全性提示（但需谨慎措辞） |
| `Tox_32tasks/` | 32 个细胞系 × train/test | 分细胞系毒性 | 细分毒性，价值中等 |
| `Accum_full.xlsx` | 186 × 2 | 累积性 label | 价值低 |
| `MIC_Ecoli/Saureus_*.xlsx` | 各 train/test/full | 抗菌活性 | ❌ 与本项目无关 |

## 四、对项目的实际价值排序

1. **PPB 数据集（3,921 条）** —— 唯一真正能补进暴露量链的数据。血浆蛋白结合率决定"入血后有多少是游离态（才可能起效）"。这是当前 `exposure_service` 公式里完全缺失的一维。
2. **AutoML 方法论** —— 课件强调的「多算法族交叉验证」可用本地 sklearn 复现，不依赖这个 exe。
3. **Tox 数据集** —— 可做内部参考，但**不建议对外展示**（细胞毒性浓度与食疗摄入量差几个数量级，容易误伤）。

## 五、不建议做的

| 项 | 原因 |
|---|---|
| ❌ 集成 exe 进后端 | GUI 程序，无 CLI，无法批处理 |
| ❌ 用它的分子生成模块 | 食养场景不造新分子，生成物无食用安全依据 |
| ❌ 对外展示 Tox 毒性结论 | 剂量数量级不匹配，会误导用户 |
| ❌ 追它的预训练化学语言模型 | 面向 de novo 设计，与本项目正交 |

## 六、落地建议

**不碰 exe，只取数据和思路：**

```
PPB_full.xlsx (3,921 条)
  → 训练一个 PPB 预测器（本地 sklearn/XGBoost）
  → 对 shiyang 165 个成分预测血浆蛋白结合率
  → 暴露量链补一维：游离浓度 = 估计入血量 × (1 - PPB)
  → 展示层：标注"游离态估计"，区分「入血」与「能起效的游离态」
```

**但注意**：3,921 条是通用药物数据，与中药成分的化学空间距离需要先测（实测 shiyang 165 成分对该库最大 Tanimoto 中位数 0.416），覆盖率不足时要如实标注"外推估计"。

## 七、一句话

> AutoMolDesigner 的价值在 `working_dir/datasets/` 那 3 个 Excel，不在那个 39MB 的 exe。exe 只能人工点，接不进平台；但它的 PPB 数据集能补上暴露量链缺失的"血浆蛋白结合"这一维。
