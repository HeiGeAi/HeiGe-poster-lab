---
name: HeiGe-poster-lab
description: Design and generate high-impact raster posters with convincing naked-eye 3D depth, oversized Chinese typography, cobalt-blue/hot-pink/acid-lime color clashes, glitch tearing, xerox grain, and avant-garde youth-magazine composition. Use when the user asks for 裸眼立体海报、故障艺术海报、Y2K/亚文化杂志视觉、文字冲出屏幕的封面, wants to reuse the approved “一句话，把 Crush 变成宠物！” poster look, or refers to “这种效果/这样的海报” in that established context. Supports arbitrary themes, exact copy, subjects, and landscape/portrait ratios; default to 2.35:1 when unspecified.
---

# 裸眼故障海报设计

Create the requested poster as a finished raster image. Treat spatial depth as the composition's skeleton; color and glitch texture alone never satisfy this skill.

## 选择生图引擎（每次生图前必须确认）

本 skill 支持两条生图链路。**不要默认替用户决定**，先问一句：

> 这次用 codex 内置生图能力，还是走第三方 API（如 gpt-image-2 / 其他 OpenAI 兼容接口）？

| 引擎 | 特点 | 何时选 |
|------|------|--------|
| **codex 内置生图** | 零配置，直接调用当前平台的 image-generation tool | 用户在 codex / Claude Code 等已开通内置生图的环境；或没有第三方 key |
| **第三方 API 生图** | 走 `scripts/gen.py`，支持任意 OpenAI 兼容 API，可自选模型和渠道 | 用户有自购 key / 中转渠道；或内置生图效果不满意；或需要批量 / 可复现规格 |

**确认规则**：

1. 如果用户第一次调用本 skill，或未明确说用哪种方式，**必须弹出上面的二选一问题**。
2. 如果 `~/.HeiGe-poster-lab/config.json` 或 `~/.heige-image/config.json` 已存在有效 key，且用户没明确拒绝第三方 API，可以提示：「检测到你已配置第三方 API，是否这次就用它？」
3. 用户明确说「用内置」「用 codex」「不用 API」等，走内置生图。
4. 用户明确说「用第三方」「用 gpt-image-2」「走 API」等，走第三方 API。
5. 用户把 base_url / api_key / model 直接甩给你，视为选择第三方 API。

## Start from the approved visual anchor

1. Resolve `assets/approved-reference.png` relative to this skill directory.
2. Inspect it with the available image-viewing tool before generating.
3. Pass it to the image-generation tool as a **style-and-depth reference only**, never as an edit target, unless the user explicitly asks to edit it.
4. Read [references/visual-dna.md](references/visual-dna.md) before composing the prompt.
5. Read [references/prompt-blueprint.md](references/prompt-blueprint.md) when generating or revising an image.

## Build the brief

Extract:

- exact primary headline;
- theme or transformation concept;
- requested ratio and intended platform;
- optional subject, palette, and supporting copy.

Default to 2.35:1, cobalt blue/hot pink/acid lime, one mysterious editorial subject, and at most four short supporting phrases. Ask only when the main headline or subject is genuinely unknowable; otherwise make tasteful choices and generate directly.

Preserve the user's exact wording. Select one semantic keyword as the typographic hero. Do not invent brands, logos, QR codes, or claims.

## Compose for real depth

Construct four explicit layers:

1. **Extreme foreground:** oversized headline fragments, cropped by the canvas, razor sharp, with controlled extrusion, shadow, and chromatic separation.
2. **Floating foreground:** one to three thematic symbols or torn strips at different scales; crop or overlap at least one element.
3. **Middle ground:** the subject and one theme-defining object; weave them through the typography using bidirectional occlusion.
4. **Deep background:** enlarged dark imagery, small copy, halftone, grain, and softer contrast.

Require a diagonal depth path, scale disparity, focus falloff, atmospheric contrast, glow spill, and visible cast shadows between layers. Make at least one letter pass in front of the subject and at least one subject edge pass in front of another text layer.

The primary headline should occupy 45–65% of the canvas and remain legible as a thumbnail. Favor 2–3 staggered lines over a neat centered block. Keep secondary copy subordinate.

## Generate and inspect

### 路径 A：codex 内置生图

当用户选择内置生图时：

- 用本 skill 生成的最终英文 prompt 直接调用当前平台的 image-generation tool。
- 把 `assets/approved-reference.png` 作为 style-and-depth reference 传入。
- 走单张生成，按本 skill 的 QA checklist 逐项验收。

### 路径 B：第三方 API 生图

当用户选择第三方 API 时：

- 先把需求落成规格文件 `prompts/NN-主题.md`（格式见下方「规格文件机制」）。
- 调用 `python3 scripts/gen.py --spec prompts/NN-主题.md [-ar 2.35:1] [-o outimage/NN-主题.png]`。
- 脚本自动读取 `~/.HeiGe-poster-lab/config.json` 或 fallback 到 `~/.heige-image/config.json`。
- 读取失败时，脚本会提示用户配置；你也可以在命令行显式传入 `--base-url` / `--api-key` / `--model`。

无论走哪条路径，inspect the actual output for:

- exact main headline and keyword spelling;
- obvious foreground/middle/background separation;
- real occlusion rather than a flat poster with drop shadows;
- readable hierarchy at thumbnail scale;
- clean anatomy and theme-relevant symbols;
- requested aspect ratio;
- absence of logos, watermarks, QR codes, and accidental UI panels.

If it fails, make one targeted revision at a time. Prioritize fixes in this order:

1. main text accuracy;
2. depth and occlusion;
3. headline scale and hierarchy;
4. subject clarity;
5. texture and secondary copy.

Never call a result “裸眼立体” merely because it uses extruded type. Regenerate when the foreground does not visibly crop, overlap, or cast into the middle ground.

## 第三方 API 生图引擎配置

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

脚本只依赖 `httpx`。`playwright` 不需要，因为裸眼海报走 API 引擎，不走 HTML 渲染。

### 2. 配置 API

三选一，优先级从高到低：**命令行参数 > 环境变量 > 配置文件**。

**方式一：本 skill 独立配置文件（推荐）**

```bash
mkdir -p ~/.HeiGe-poster-lab
cat > ~/.HeiGe-poster-lab/config.json <<EOF
{"base_url": "https://api.openai.com/v1", "api_key": "sk-xxx", "model": "gpt-image-2"}
EOF
```

参考 `config.example.json`。

**方式二：环境变量**

```bash
export HEIGE_POSTER_LAB_BASE_URL=https://api.openai.com/v1
export HEIGE_POSTER_LAB_API_KEY=sk-xxx
export HEIGE_POSTER_LAB_MODEL=gpt-image-2
```

**方式三：命令行参数**

```bash
python3 scripts/gen.py --base-url https://api.openai.com/v1 --api-key sk-xxx --model gpt-image-2 --spec prompts/01-示例-裸眼故障海报.md
```

### 3. 复用 heige-image 配置

如果用户已经配过 heige-image，本 skill 会自动 fallback 读取 `~/.heige-image/config.json` 或对应环境变量 `HEIGE_IMAGE_*`。用户无需重复填 key。

### 4. 常用命令

```bash
# 规格文件出图（主推）
python3 scripts/gen.py --spec prompts/01-示例-裸眼故障海报.md -ar 16:9

# 临时直给提示词
python3 scripts/gen.py --prompt "完整英文 prompt" -ar 16:9 -o outimage/test.png

# 批量出图
python3 scripts/gen.py --batch tasks.json --workers 2
```

`tasks.json` 格式：

```json
[
  {"prompt": "英文 prompt 1", "output": "outimage/a.png", "aspect_ratio": "16:9"},
  {"prompt": "英文 prompt 2", "output": "outimage/b.png", "aspect_ratio": "3:4"}
]
```

批量张数超 `--max-n`（默认 6）会被成本护栏直接拦。

> 宽高比说明：第三方 API 只有三档物理尺寸（1024x1024 / 1536x1024 / 1024x1536）。1:1 / 3:2 / 2:3 精确匹配；其余比例（含默认的 2.35:1）会近似映射到最近档位，脚本日志会显式提示实际尺寸。

## 图生图 / 编辑（可选）

如需基于已有图片做裸眼故障风格的修改或多图合成，使用 `scripts/edit.py`：

```bash
# 单图编辑
python3 scripts/edit.py --input photo.jpg --prompt "换成裸眼故障海报风格，背景加深蓝黑，加红蓝错位故障" -ar 16:9 -o outimage/edited.png

# 多图合成（图1=基底，图2=参考）
python3 scripts/edit.py --input scene.jpg --input face.jpg --prompt "以图1为场景，融入图2人物，保持裸眼纵深构图" -ar 16:9 -o outimage/merged.png
```

配置约定与 `gen.py` 完全一致。

## 规格文件机制

走第三方 API 时，**规格即真相**。每个任务先落规格文件 `prompts/NN-主题.md`，再出图。改图只改规格里的最终 Prompt 和 Invariant 清单，不绕过规格直接改 prompt。

规格文件固定三块：

```markdown
# NN-主题名

## Brief

- 主题：一句话概括
- 主标题：用户给定的精确文字
- 比例：2.35:1 / 16:9 / 3:4 等
- 平台：公众号封面 / 小红书 / 其他

## 最终 Prompt

```text
（送进 API 的完整英文 prompt，脚本只读这一块）
```

## Invariant 清单

- 主标题：xxx
- 主色：#1111F4
- 强调色：#FF174F
- 反色：#B9FF4A
- 比例：xxx
- 主体：xxx
```

`scripts/gen.py` 只读取「最终 Prompt」小标题下第一个围栏代码块。比例可以写在 Brief 里，也可以用 `-ar` 命令行覆盖。

参考实例：`prompts/01-示例-裸眼故障海报.md`。

## Deliver

Show the final image directly. Briefly state:

- which engine was used（内置 / 第三方 API + 模型）;
- the chosen spatial device and palette;
- the output path if generated via the API script.

Do not bury the image under a long design explanation.

## 成本护栏

- 第三方 API 引擎单次张数上限默认 6，可在 `scripts/gen.py` 用 `--max-n` 显式调高。
- 回炉最多 1 轮。1 轮后还不行就降级处理（换构图重写 prompt，或换引擎），别无限重试烧钱。
- 版式渲染（HTML 截图）不在本 skill 的主路径里，裸眼海报以 API 画面叙事为主。
