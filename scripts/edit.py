#!/usr/bin/env python3
"""HeiGe-poster-lab 图生图 / 图片编辑脚本 - 走任意 OpenAI 兼容图像编辑 API。

复刻 heige-image 的 edit.py 链路，命名空间独立，同时 fallback 到 heige-image 配置。

用法:
    # 单张编辑
    python scripts/edit.py --input photo.jpg --prompt "把背景换成雪景" -o outimage/edited.png

    # 多图输入（图1=基底，图2+=人脸/风格参考）
    python scripts/edit.py --input scene.jpg --input face.jpg \
        --prompt "以图1为场景基底，把图2人物自然融入中央" -o outimage/merged.png

    # 批量编辑
    python scripts/edit.py --batch tasks.json [--workers 2]
"""

from __future__ import annotations

import argparse
import base64
import binascii
import io
import json
import mimetypes
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import httpx
except ImportError:
    print("错误: 需要 httpx 库，请执行: pip install httpx", file=sys.stderr)
    sys.exit(1)

try:
    from .image_output import (
        ImageResponseError,
        OutputPathError,
        atomic_write_image,
        validate_image_bytes,
        validate_image_response,
        validate_output_path,
    )
except ImportError:
    from image_output import (
        ImageResponseError,
        OutputPathError,
        atomic_write_image,
        validate_image_bytes,
        validate_image_response,
        validate_output_path,
    )

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-image-2"
CONFIG_FILE = Path.home() / ".HeiGe-poster-lab" / "config.json"
HEIGE_CONFIG_FILE = Path.home() / ".heige-image" / "config.json"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outimage"

VALID_ASPECT_RATIOS = [
    "1:1", "16:9", "9:16", "4:3", "3:4",
    "3:2", "2:3", "21:9", "5:4", "4:5",
    "2.35:1",
]

ASPECT_SIZE_MAP = {
    "1:1": "1024x1024",
    "2.35:1": "1536x1024",
    "16:9": "1536x1024",
    "9:16": "1024x1536",
    "4:3": "1536x1024",
    "3:4": "1024x1536",
    "3:2": "1536x1024",
    "2:3": "1024x1536",
    "21:9": "1536x1024",
    "5:4": "1536x1024",
    "4:5": "1024x1536",
}

SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_IMAGE_SIZE_MB = 10
TIMEOUT_SECONDS = 600
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

_print_lock = threading.Lock()


def _safe_print(msg, *, file=None):
    with _print_lock:
        print(msg, file=file or sys.stdout, flush=True)


# ---------------------------------------------------------------------------
# API 配置管理
# ---------------------------------------------------------------------------

def _load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _load_self_config() -> dict:
    return _load_config(CONFIG_FILE)


def _load_fallback_config() -> dict:
    return _load_config(HEIGE_CONFIG_FILE)


def resolve_api_key(cli_key: str | None = None, config: dict | None = None) -> str:
    if cli_key:
        return cli_key.strip()

    env_key = os.environ.get("HEIGE_POSTER_LAB_API_KEY", "").strip()
    if env_key:
        return env_key

    if config is None:
        config = _load_self_config()
    file_key = (config.get("api_key") or "").strip()
    if file_key:
        return file_key

    env_key = os.environ.get("HEIGE_IMAGE_API_KEY", "").strip()
    if env_key:
        return env_key

    fallback_config = _load_fallback_config()
    file_key = (fallback_config.get("api_key") or "").strip()
    if file_key:
        return file_key

    print(
        "错误: 未找到 API Key。请通过以下方式之一配置:\n"
        f"  1. 写配置文件 {CONFIG_FILE}，内容: "
        '{"base_url": "https://api.openai.com/v1", "api_key": "sk-xxx", "model": "gpt-image-2"}\n'
        "  2. 设置环境变量 HEIGE_POSTER_LAB_API_KEY=sk-xxx\n"
        "  3. 使用 --api-key sk-xxx 命令行参数\n"
        "  4. 复用 heige-image 配置: ~/.heige-image/config.json 或 HEIGE_IMAGE_API_KEY",
        file=sys.stderr,
    )
    sys.exit(1)


def resolve_base_url(cli_base_url: str | None = None, config: dict | None = None) -> str:
    if cli_base_url:
        base = cli_base_url.strip()
    elif os.environ.get("HEIGE_POSTER_LAB_BASE_URL", "").strip():
        base = os.environ["HEIGE_POSTER_LAB_BASE_URL"].strip()
    else:
        if config is None:
            config = _load_self_config()
        base = (config.get("base_url") or "").strip() or DEFAULT_BASE_URL

    if base == DEFAULT_BASE_URL and not os.environ.get("HEIGE_POSTER_LAB_BASE_URL"):
        fallback_config = _load_fallback_config()
        fallback_base = (fallback_config.get("base_url") or "").strip()
        env_fallback = os.environ.get("HEIGE_IMAGE_BASE_URL", "").strip()
        base = env_fallback or fallback_base or base

    return base.rstrip("/")


def resolve_model(cli_model: str | None = None, config: dict | None = None) -> str:
    if cli_model:
        return cli_model.strip()
    env_model = os.environ.get("HEIGE_POSTER_LAB_MODEL", "").strip()
    if env_model:
        return env_model
    if config is None:
        config = _load_self_config()
    self_model = (config.get("model") or "").strip()
    if self_model:
        return self_model

    fallback_config = _load_fallback_config()
    env_fallback = os.environ.get("HEIGE_IMAGE_MODEL", "").strip()
    fallback_model = (fallback_config.get("model") or "").strip()
    return env_fallback or fallback_model or DEFAULT_MODEL


# ---------------------------------------------------------------------------
# 图片读取
# ---------------------------------------------------------------------------

def read_image_bytes(image_path: str) -> tuple[bytes, str]:
    path = Path(image_path)

    if not path.exists():
        raise FileNotFoundError(f"图片文件不存在: {image_path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_IMAGE_FORMATS:
        raise ValueError(
            f"不支持的图片格式 '{suffix}'，支持: {', '.join(sorted(SUPPORTED_IMAGE_FORMATS))}"
        )

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_IMAGE_SIZE_MB:
        raise ValueError(f"图片过大 ({size_mb:.1f}MB)，建议 < {MAX_IMAGE_SIZE_MB}MB")

    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type or not mime_type.startswith("image/"):
        mime_type = "image/png"

    return path.read_bytes(), mime_type


def _suffix_from_mime(mime_type: str) -> str:
    map_ = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    return map_.get(mime_type, ".png")


# ---------------------------------------------------------------------------
# 请求
# ---------------------------------------------------------------------------

def _request_once(
    prompt: str,
    images: list,
    timeout: int,
    api_key: str,
    base_url: str,
    model: str,
    size: str,
) -> httpx.Response:
    url = f"{base_url}/images/edits"

    parts = []
    for idx, (image_bytes, mime_type) in enumerate(images):
        filename = f"image{idx}{_suffix_from_mime(mime_type)}"
        parts.append((filename, io.BytesIO(image_bytes), mime_type))

    if len(parts) == 1:
        files = {"image": parts[0]}
    else:
        files = [("image[]", part) for part in parts]

    with httpx.Client(timeout=timeout) as client:
        data = {
            "model": model,
            "prompt": prompt,
            "size": size,
        }
        return client.post(
            url,
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {api_key}"},
        )


# ---------------------------------------------------------------------------
# 核心编辑逻辑
# ---------------------------------------------------------------------------

def _edit_core(
    input_image,
    prompt: str,
    api_key: str,
    base_url: str,
    model: str,
    aspect_ratio: str = "1:1",
    output_path: str | None = None,
    max_retries: int = 3,
    task_label: str = "",
) -> dict:
    tag = f"[HeiGe-poster-lab 编辑{' ' + task_label if task_label else ''}]"
    if output_path is None:
        output_path = str(OUTPUT_DIR / "output.png")
    try:
        output_path = str(validate_output_path(output_path))
    except (OSError, OutputPathError) as e:
        return {"success": False, "error": f"输出路径校验失败: {e}"}

    if isinstance(input_image, (str, Path)):
        input_paths = [str(input_image)]
    elif isinstance(input_image, list):
        input_paths = [str(p) for p in input_image]
    else:
        return {"success": False, "error": "input 必须是图片路径或路径列表"}

    try:
        images = [read_image_bytes(p) for p in input_paths]
    except (OSError, ValueError) as e:
        return {"success": False, "error": f"读取图片失败: {e}"}

    resolved_size = ASPECT_SIZE_MAP.get(aspect_ratio, "1024x1024")

    _safe_print(f"{tag} 正在编辑图片...")
    _safe_print(f"{tag}   输入: {input_paths} | 宽高比: {aspect_ratio} -> {resolved_size}")

    resp = None
    last_error = None
    elapsed = 0.0

    for attempt in range(max_retries + 1):
        if attempt > 0:
            delay = min(2 ** attempt, 60)
            _safe_print(f"{tag} 第 {attempt}/{max_retries} 次重试，等待 {delay}s ...")
            time.sleep(delay)

        _safe_print(f"{tag} 发送请求 (attempt {attempt + 1})")

        t0 = time.time()
        try:
            resp = _request_once(prompt, images, TIMEOUT_SECONDS, api_key, base_url, model, resolved_size)
        except httpx.TimeoutException:
            last_error = "请求超时"
            _safe_print(f"{tag} 请求超时", file=sys.stderr)
            continue
        except httpx.ConnectError as e:
            last_error = f"连接失败: {e}"
            _safe_print(f"{tag} 连接失败: {e}", file=sys.stderr)
            continue

        elapsed = time.time() - t0

        if resp.status_code == 200:
            _safe_print(f"{tag} API 响应成功，耗时 {elapsed:.1f}s")
            break

        if resp.status_code in RETRYABLE_STATUS_CODES and attempt < max_retries:
            try:
                err_body = resp.json()
                err_msg = err_body.get("error", {}).get("message", resp.text[:200])
            except Exception:
                err_msg = resp.text[:200]
            last_error = f"HTTP {resp.status_code}: {err_msg}"
            _safe_print(f"{tag} 收到 {resp.status_code}，将重试", file=sys.stderr)
            continue

        try:
            err_detail = json.dumps(resp.json(), indent=2, ensure_ascii=False)[:500]
        except Exception:
            err_detail = resp.text[:500]
        return {"success": False, "error": f"HTTP {resp.status_code}: {err_detail}"}
    else:
        return {"success": False, "error": f"重试 {max_retries} 次仍然失败。最后错误: {last_error}"}

    data = resp.json()
    image_url = data.get("data", [{}])[0].get("url")
    b64_data = data.get("data", [{}])[0].get("b64_json")

    if image_url:
        _safe_print(f"{tag} 下载图片 from: {image_url}")
        try:
            with httpx.stream("GET", image_url, timeout=60, follow_redirects=True) as img_resp:
                img_resp.raise_for_status()
                image_bytes = validate_image_response(img_resp)
        except (httpx.HTTPError, ImageResponseError) as e:
            return {"success": False, "error": f"图片下载校验失败: {e}"}
    elif b64_data:
        _safe_print(f"{tag} 解码 base64 图片...")
        try:
            image_bytes = validate_image_bytes(base64.b64decode(b64_data, validate=True))
        except (binascii.Error, ValueError, ImageResponseError) as e:
            return {"success": False, "error": f"base64 图片校验失败: {e}"}
    else:
        return {"success": False, "error": f"API 响应中未找到图片数据: {data}"}

    try:
        out = atomic_write_image(output_path, image_bytes)
    except (OSError, OutputPathError, ImageResponseError) as e:
        return {"success": False, "error": f"图片写入失败: {e}"}

    size_kb = len(image_bytes) / 1024
    _safe_print(f"{tag} 编辑完成，大小 {size_kb:.0f}KB -> {out}")

    return {
        "success": True,
        "path": str(out),
        "size_kb": round(size_kb, 1),
        "elapsed": round(elapsed, 1),
    }


def edit(
    input_image,
    prompt: str,
    api_key: str,
    base_url: str,
    model: str,
    aspect_ratio: str = "1:1",
    output_path: str | None = None,
    max_retries: int = 3,
) -> str:
    result = _edit_core(
        input_image=input_image,
        prompt=prompt,
        api_key=api_key,
        base_url=base_url,
        model=model,
        aspect_ratio=aspect_ratio,
        output_path=output_path,
        max_retries=max_retries,
    )
    if not result["success"]:
        print(f"错误: {result['error']}", file=sys.stderr)
        sys.exit(1)
    return result["path"]


def edit_batch(
    tasks: list,
    api_key: str,
    base_url: str,
    model: str,
    workers: int = 0,
    max_retries: int = 3,
) -> list:
    num_tasks = len(tasks)

    if workers <= 0:
        workers = min(num_tasks, 2)
    workers = max(1, min(workers, num_tasks))

    print(f"[HeiGe-poster-lab 编辑批量] 共 {num_tasks} 个任务，并发数: {workers}")

    t_start = time.time()
    results = [None] * num_tasks

    def _run_task(index: int, task: dict) -> tuple:
        result = _edit_core(
            input_image=task["input"],
            prompt=task["prompt"],
            api_key=api_key,
            base_url=base_url,
            model=model,
            aspect_ratio=task.get("aspect_ratio", "1:1"),
            output_path=task["output"],
            max_retries=max_retries,
            task_label=f"#{index + 1}",
        )
        result["index"] = index
        return index, result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_run_task, i, t): i
            for i, t in enumerate(tasks)
        }
        for future in as_completed(futures):
            idx, result = future.result()
            results[idx] = result
            status = "OK" if result["success"] else "FAIL"
            _safe_print(f"[HeiGe-poster-lab 编辑批量] 任务 #{idx + 1} {status}")

    t_total = time.time() - t_start
    ok = sum(1 for r in results if r and r["success"])
    print(f"\n[HeiGe-poster-lab 编辑批量] 全部完成: {ok}/{num_tasks} 成功，总耗时 {t_total:.1f}s")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="HeiGe-poster-lab - 走任意 OpenAI 兼容图像编辑 API 的图生图脚本",
    )

    parser.add_argument(
        "--base-url", default=None,
        help="API 基址（优先级 CLI > 环境变量 HEIGE_POSTER_LAB_BASE_URL > 配置文件）",
    )
    parser.add_argument(
        "--api-key", default=None,
        help="API Key（优先级 CLI > 环境变量 HEIGE_POSTER_LAB_API_KEY > 配置文件）",
    )
    parser.add_argument(
        "--model", default=None,
        help="模型名（优先级 CLI > 环境变量 HEIGE_POSTER_LAB_MODEL > 配置文件 > 默认 gpt-image-2）",
    )

    parser.add_argument(
        "--input", "-i", action="append", default=None,
        help="输入图片路径，可多次传入（图1=基底，图2+=参考）",
    )
    parser.add_argument(
        "--prompt", "-p", default=None,
        help="编辑描述",
    )
    parser.add_argument(
        "--batch", "-b", default=None, metavar="JSON_FILE",
        help="批量任务 JSON 文件路径（与 --input/--prompt 互斥）",
    )

    parser.add_argument(
        "--aspect-ratio", "-ar", default="1:1",
        choices=VALID_ASPECT_RATIOS,
        help="输出宽高比（默认 1:1）",
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="输出文件路径（默认 outimage/output.png）",
    )

    parser.add_argument(
        "--workers", "-w", type=int, default=0,
        help="批量并发 worker 数（默认: 自动）",
    )

    parser.add_argument(
        "--retry", "-r", type=int, default=3,
        choices=range(0, 11), metavar="0-10",
        help="每个任务的最大重试次数（默认: 3）",
    )

    args = parser.parse_args()

    if args.batch:
        if args.input or args.prompt:
            parser.error("--batch 与 --input/--prompt 互斥")
        batch_path = Path(args.batch)
        if not batch_path.exists():
            print(f"错误: 批量任务文件不存在: {batch_path}", file=sys.stderr)
            sys.exit(1)
        try:
            tasks = json.loads(batch_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"错误: 解析批量任务文件失败: {e}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(tasks, list) or not tasks:
            print("错误: 批量任务文件必须是非空 JSON 数组", file=sys.stderr)
            sys.exit(1)

        config = _load_self_config()
        base_url = resolve_base_url(args.base_url, config)
        api_key = resolve_api_key(args.api_key, config)
        model = resolve_model(args.model, config)

        results = edit_batch(
            tasks=tasks,
            api_key=api_key,
            base_url=base_url,
            model=model,
            workers=args.workers,
            max_retries=args.retry,
        )
        print("\n" + json.dumps(results, indent=2, ensure_ascii=False))
        if any(not r["success"] for r in results if r):
            sys.exit(1)
        return

    if not args.input or not args.prompt:
        parser.error("单图编辑必须提供 --input 和 --prompt")

    config = _load_self_config()
    base_url = resolve_base_url(args.base_url, config)
    api_key = resolve_api_key(args.api_key, config)
    model = resolve_model(args.model, config)

    output_path = args.output or str(OUTPUT_DIR / "output.png")
    edit(
        input_image=args.input,
        prompt=args.prompt,
        api_key=api_key,
        base_url=base_url,
        model=model,
        aspect_ratio=args.aspect_ratio,
        output_path=output_path,
        max_retries=args.retry,
    )


if __name__ == "__main__":
    main()
