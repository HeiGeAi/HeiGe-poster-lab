# HeiGe-poster-lab

一个 Claude Code / Codex skill，用于生成具有**裸眼 3D 纵深、故障艺术撕裂、Y2K 亚文化杂志风格**的高冲击海报。

它把视觉风格控制、双引擎生图链路和规格文件机制打包在一起：既可以零配置走 codex 内置生图，也可以接任意 OpenAI 兼容的第三方图像 API。

## 核心能力

- **裸眼立体纵深**：强制四层构图（极端前景 / 漂浮前景 / 中景 / 深景），要求文字与主体之间有真实的双向遮挡。
- **故障杂志质感**：电光蓝 #1111F4、荧光粉 #FF174F、酸性绿 #B9FF4A 的撞色，叠加 xerox 颗粒、半调、错位、撕纸边缘。
- **双引擎生图**：
  - codex 内置 image-generation tool（零配置）
  - 第三方 API：`scripts/gen.py` + `scripts/edit.py`，支持 gpt-image-2 等任意 OpenAI 兼容接口
- **规格文件驱动**：每个任务先落 `prompts/NN-主题.md`，prompt 不漂移，改图可复现。

## 效果示例

由本 skill 生成的裸眼故障海报样张：

### 一句话，把 Crush 变成宠物！

![Crush](examples/02-Crush.png)

### 凌晨三点的代码还在跑

![凌晨三点](examples/03-凌晨三点.png)

### 咖啡凉了，方案没过

![咖啡凉了](examples/04-咖啡凉了.png)

## 文件结构

```
HeiGe-poster-lab/
├── SKILL.md                    # skill 入口：风格规则 + 引擎选择 + 使用流程
├── agents/openai.yaml          # skill 元数据
├── config.example.json         # API 配置示例
├── requirements.txt            # Python 依赖
├── README.md                   # 本文件
├── LICENSE                     # MIT
├── .gitignore
├── assets/
│   ├── approved-reference.png  # 官方风格锚点参考图
│   └── icon.svg
├── examples/                   # 示例输出海报
├── references/
│   ├── visual-dna.md           # 视觉 DNA：层、色板、字体、构图
│   └── prompt-blueprint.md     # 英文 prompt 模板
├── prompts/                    # 规格文件目录
│   └── 01-示例-裸眼故障海报.md
└── scripts/
    ├── gen.py                  # 第三方 API 文生图
    ├── edit.py                 # 第三方 API 图生图 / 多图合成
    └── image_output.py         # PNG 校验 + 原子写入
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API（仅第三方 API 模式需要）

```bash
mkdir -p ~/.HeiGe-poster-lab
cat > ~/.HeiGe-poster-lab/config.json <<EOF
{"base_url": "https://api.openai.com/v1", "api_key": "sk-xxx", "model": "gpt-image-2"}
EOF
chmod 600 ~/.HeiGe-poster-lab/config.json  # 文件含 API key，禁止同机其他用户读
```

也支持环境变量：

```bash
export HEIGE_POSTER_LAB_BASE_URL=https://api.openai.com/v1
export HEIGE_POSTER_LAB_API_KEY=sk-xxx
export HEIGE_POSTER_LAB_MODEL=gpt-image-2
```

如果已经配过 [heige-image](https://github.com/HeiGeAi/heige-image)，本 skill 会自动 fallback 读取 `~/.heige-image/config.json`，无需重复填 key。

> 安全提示：config.json 里的 base_url 请只填你信任的端点。脚本只接受 https 图片下载地址，但恶意端点仍可能返回误导内容。

### 3. 出图

```bash
# 规格文件出图（推荐）
python3 scripts/gen.py --spec prompts/01-示例-裸眼故障海报.md -ar 16:9

# 临时直给提示词
python3 scripts/gen.py --prompt "完整英文 prompt" -ar 16:9 -o outimage/test.png

# 批量出图
python3 scripts/gen.py --batch tasks.json --workers 2
```

> 宽高比说明：第三方 API 只有三档物理尺寸（1024x1024 / 1536x1024 / 1024x1536）。1:1 / 3:2 / 2:3 精确匹配；其余比例（含 2.35:1、16:9、21:9 等）会近似映射到最近档位，并在日志中显式提示实际尺寸。

### 4. 图生图 / 编辑

```bash
# 单图编辑
python3 scripts/edit.py --input photo.jpg --prompt "换成裸眼故障海报风格" -ar 16:9 -o outimage/edited.png

# 多图合成（图1=基底，图2=参考）
python3 scripts/edit.py --input scene.jpg --input face.jpg --prompt "以图1为场景，融入图2人物" -ar 16:9 -o outimage/merged.png
```

## 在 Claude Code / Codex 中使用

把本目录作为 skill 安装到 Claude Code 或 Codex 后，调用时它会先问你：

> 这次用 codex 内置生图能力，还是走第三方 API？

- 选内置：直接调 image-generation tool，零配置。
- 选第三方：按规格文件调用 `scripts/gen.py`，需要配置 API key。

## 配置优先级

命令行参数 > 环境变量 > `~/.HeiGe-poster-lab/config.json` > `~/.heige-image/config.json` > 默认值。注意：仅当本 skill 配置未设置（或显式写成 OpenAI 官方默认值）时，才会 fallback 读取 heige-image 配置；base_url 显式写了其他值时以本 skill 配置为准。

## 协议

MIT License. Copyright (c) 2026 HeiGeAi (Blake Xu).

## 致谢

生图链路参考了 [heige-image](https://github.com/HeiGeAi/heige-image) 的设计。
