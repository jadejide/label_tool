import csv
import html
import io
import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="数字题人工标注工具", layout="wide")

# =========================
# 配置
# =========================
UNSELECTED = "未选择"
BLOOM_LEVELS = [UNSELECTED, "记忆", "理解", "应用", "分析", "评价", "创造"]
CORE_LITERACIES = [
    "抽象能力", "运算能力", "几何直观", "空间观念", "推理能力",
    "数据观念", "模型观念", "应用意识", "创新意识",
]
PRIMARY_OPTIONS = [UNSELECTED] + CORE_LITERACIES

TASKS: Dict[str, Dict[str, str]] = {
    "teacher1": {"label": "教师 1", "data_file": "teacher_1.json"},
    "teacher2": {"label": "教师 2", "data_file": "teacher_2.json"},
    "teacher3": {"label": "教师 3", "data_file": "teacher_3.json"},
}
task_from_url = st.query_params.get("task", "teacher1")
if task_from_url not in TASKS:
    st.error("无效任务链接")
    st.stop()

active_task = task_from_url
task_label = TASKS[active_task]["label"]

with st.sidebar:
    st.markdown(f"**当前任务：{task_label}**")

BASE_DIR = Path(__file__).parent

# =========================
# 样式
# =========================
st.markdown(
    """
<style>
.block-container {
    padding-top: 2rem;
    padding-bottom: 1.5rem;
}
[data-testid="stImage"] img {
    max-height: 360px !important;
    width: auto !important;
    object-fit: contain;
    border-radius: 8px;
    border: 1px solid #e5e7eb;
    padding: 4px;
    background: white;
}
.small-muted { color: #667085; font-size: 0.92rem; }
.status-line { font-size: 0.92rem; color: #667085; margin-top: -0.2rem; margin-bottom: 0.6rem; }
.model-card {
    border: 1px solid #dbeafe;
    background: #f8fbff;
    border-radius: 14px;
    padding: 12px 14px;
}
.model-title { font-weight: 700; margin-bottom: 0.45rem; }
.model-row { margin: 0.25rem 0; }
.math-text {
    font-size: 19px;
    line-height: 1.9;
    word-break: break-word;
    white-space: normal;
}
.math-text.compact { font-size: 17px; line-height: 1.75; }
.katex-host {
    font-size: 19px;
    line-height: 1.9;
    word-break: break-word;
}
.katex-host.compact {
    font-size: 17px;
    line-height: 1.75;
}
.katex-host .katex { font-size: 1em; }
.katex-host .katex-display { margin: 0.35em 0; overflow-x: auto; overflow-y: hidden; }
.katex-host br { line-height: 1.9; }
.option-card {
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: 12px 14px;
    background: #fff;
    display: grid;
    grid-template-columns: 32px 1fr;
    gap: 10px;
    align-items: start;
    margin-bottom: 10px;
}
.option-label {
    width: 28px;
    height: 28px;
    border-radius: 999px;
    background: #eff6ff;
    color: #2563eb;
    font-weight: 700;
    display: grid;
    place-items: center;
    font-size: 13px;
    margin-top: 4px;
}
.frac {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    vertical-align: middle;
    margin: 0 0.08em;
    min-width: 1.4em;
}
.frac > span:first-child {
    display: block;
    padding: 0 0.18em 0.05em;
    border-bottom: 1.5px solid currentColor;
    line-height: 1.15;
}
.frac > span:last-child {
    display: block;
    padding: 0.05em 0.18em 0;
    line-height: 1.15;
    font-size: 0.95em;
}
.cases {
    display: inline-flex;
    align-items: stretch;
    vertical-align: middle;
    margin: 0 0.12em;
}
.cases-brace {
    font-size: 2.3em;
    line-height: 0.92;
    transform: scaleY(1.18);
    padding-right: 0.08em;
    font-family: Georgia, "Times New Roman", serif;
}
.cases-lines {
    display: inline-flex;
    flex-direction: column;
    gap: 0.18em;
    padding-top: 0.12em;
}
.formula-line { white-space: nowrap; }
.placeholder-line {
    display: inline-block;
    min-width: 4.8em;
    border-bottom: 1.6px solid #64748b;
    transform: translateY(-0.08em);
}
.sep-line { display: block; height: 10px; }
.sqrt { display: inline-flex; align-items: flex-start; white-space: nowrap; vertical-align: middle; }
.sqrt-sign { font-size: 1.08em; line-height: 1; padding-right: 1px; }
.sqrt-body { border-top: 1.5px solid currentColor; padding: 0 2px 0 3px; line-height: 1.2; }
.overset { display: inline-flex; flex-direction: column; align-items: center; line-height: 1; vertical-align: middle; }
.overset-top { font-size: 0.7em; margin-bottom: 1px; }
.overset-base { line-height: 1; }
.saved-badge { color: #15803d; font-weight: 700; }
.draft-badge { color: #b45309; font-weight: 700; }
.empty-badge { color: #64748b; font-weight: 700; }
</style>
""",
    unsafe_allow_html=True,
)


# =========================
# 数据读取
# =========================
def read_json_file(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"未找到文件：{path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


def resolve_data_file(config_name: str) -> Path:
    raw = TASKS[config_name]["data_file"]
    p = Path(raw)
    if p.is_absolute():
        return p
    candidates = [BASE_DIR / raw, BASE_DIR / "data" / raw, BASE_DIR / raw.replace("data/", "")]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


# =========================
# 文本与公式渲染
# =========================
def normalize_text(text: Any) -> str:
    s = "" if text is None else str(text)
    s = s.replace("\u00a0", " ")
    s = s.replace(r"\;", " ").replace(r"\,", " ")
    s = s.replace(" \n", "\n").replace("\n ", "\n")
    s = s.replace("\n", "\n")
    return s.strip()


def escape_html(text: str) -> str:
    return html.escape(text, quote=False)


def looks_like_tex(text: str) -> bool:
    tex_markers = [
        "\\frac", "\\sqrt", "\\begin{", "\\end{", "\\left", "\\right",
        "\\times", "\\div", "\\pm", "\\cdot", "\\le", "\\ge",
        "\\angle", "\\triangle", "\\sin", "\\cos", "\\tan", "\\log",
        "\\sum", "\\int", "\\lim", "\\alpha", "\\beta", "\\theta",
        "^", "_",
    ]
    return any(marker in text for marker in tex_markers)


def build_katex_html(text: str, compact: bool = False) -> str:
    normalized = normalize_text(text)
    escaped = escape_html(normalized).replace("\n", "<br>")
    css_class = "katex-host compact" if compact else "katex-host"

    has_delimiters = any(token in normalized for token in ["$$", "$", "\\(", "\\)", "\\[", "\\]"])
    if looks_like_tex(normalized) and not has_delimiters:
        content = f"\\({escaped}\\)"
    else:
        content = escaped

    delimiters = json.dumps([
        {"left": "$$", "right": "$$", "display": True},
        {"left": "\\[", "right": "\\]", "display": True},
        {"left": "\\(", "right": "\\)", "display": False},
        {"left": "$", "right": "$", "display": False},
    ], ensure_ascii=False)

    return """
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
    <div class="{css_class}" id="katex-content">{content}</div>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>
    <script>
      const renderKatex = () => {{
        const host = document.getElementById('katex-content');
        if (!host || typeof renderMathInElement !== 'function') return;
        renderMathInElement(host, {{
          delimiters: {delimiters},
          throwOnError: false,
          strict: 'ignore',
          trust: true
        }});
      }};

      const startKatex = () => {{
        if (typeof renderMathInElement === 'function') {{
          renderKatex();
          return;
        }}
        setTimeout(startKatex, 120);
      }};

      if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', startKatex);
      }} else {{
        startKatex();
      }}
      setTimeout(startKatex, 350);
      setTimeout(startKatex, 900);
    </script>
    """.format(css_class=css_class, content=content, delimiters=delimiters)


def render_text_block(text: Any, compact: bool = False) -> None:
    raw = "" if text is None else str(text)
    normalized = normalize_text(raw)
    if not normalized:
        st.markdown('<div class="small-muted">暂无内容</div>', unsafe_allow_html=True)
        return
    html_content = build_katex_html(normalized, compact=compact)
    height = 110 if compact else 260
    extra = max(0, normalized.count("\n") - 1) * 32
    components.html(html_content, height=height + extra, scrolling=TRUE)


def render_options(options: List[Dict[str, Any]]) -> None:
    if not options:
        return
    for opt in options:
        label = escape_html(str(opt.get("index", "")))
        option_html = build_katex_html(str(opt.get("text", "")), compact=True)
        col1, col2 = st.columns([1, 18], vertical_alignment="top")
        with col1:
            st.markdown(f'<div class="option-label">{label}</div>', unsafe_allow_html=True)
        with col2:
            components.html(option_html, height=110, scrolling=False)
    for opt in options:
        imgs = opt.get("images") or []
        if imgs:
            render_images(imgs)

def resolve_media_path(raw_path: str) -> Optional[Path]:
    if not raw_path:
        return None
    p = Path(raw_path)
    candidates = [
        BASE_DIR / p,
        BASE_DIR / p.name,
        BASE_DIR / "images" / p.name,
        BASE_DIR / "data" / p,
        BASE_DIR / "data" / p.name,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def render_images(image_list: List[str]) -> None:
    for img in image_list or []:
        p = resolve_media_path(img)
        if p and p.exists():
            st.image(str(p))
        else:
            st.caption(f"图片未找到：{img}")


# =========================
# 数据组织
# =========================
def get_record_uid(record: Dict[str, Any], idx: int) -> str:
    return str(record.get("id") or record.get("sample_id") or f"item_{idx + 1}")


def load_base_records(task_key: str) -> List[Dict[str, Any]]:
    path = resolve_data_file(task_key)
    data = read_json_file(path)
    if not isinstance(data, list):
        raise ValueError(f"数据文件必须是列表：{path}")
    return data


def load_saved_annotations(task_key: str) -> Dict[str, Dict[str, Any]]:
    data = st.session_state.get(f"imported_saved::{task_key}", {})
    return deepcopy(data) if isinstance(data, dict) else {}


def load_drafts(task_key: str) -> Dict[str, Dict[str, Any]]:
    data = st.session_state.get(f"imported_drafts::{task_key}", {})
    return deepcopy(data) if isinstance(data, dict) else {}


def record_is_saved(record_uid: str, saved_map: Dict[str, Dict[str, Any]]) -> bool:
    saved = saved_map.get(record_uid) or {}
    return bool(saved.get("human_bloom_level")) and bool(saved.get("human_core_literacy_primary"))


def get_draft_status(record_uid: str, drafts: Dict[str, Dict[str, Any]]) -> bool:
    draft = drafts.get(record_uid) or {}
    return any(str(draft.get(k, "")).strip() for k in [
        "human_bloom_level", "human_core_literacy_primary", "human_comment_bloom", "human_comment_core"
    ]) or bool(draft.get("human_core_literacy_candidates"))


def build_working_record(base_record: Dict[str, Any], saved: Optional[Dict[str, Any]], draft: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = deepcopy(base_record)
    if saved:
        merged.update(saved)
    if draft:
        merged.update(draft)
    return merged


def sanitize_candidates(primary: str, candidates: List[str]) -> List[str]:
    clean: List[str] = []
    for x in candidates or []:
        if x in CORE_LITERACIES and x not in clean:
            clean.append(x)
    if primary in CORE_LITERACIES:
        if primary in clean:
            clean.remove(primary)
        clean = [primary] + clean
    return clean[:3]


def build_editor_state(record: Dict[str, Any]) -> Dict[str, Any]:
    bloom = record.get("human_bloom_level") or []
    if isinstance(bloom, str):
        bloom = [bloom] if bloom in BLOOM_LEVELS and bloom != UNSELECTED else []
    elif isinstance(bloom, list):
        bloom = [x for x in bloom if x in BLOOM_LEVELS and x != UNSELECTED]
    else:
        bloom = []
    primary = record.get("human_core_literacy_primary") or UNSELECTED
    if bloom not in BLOOM_LEVELS:
        bloom = UNSELECTED
    if primary not in PRIMARY_OPTIONS:
        primary = UNSELECTED
    cands = sanitize_candidates(primary if primary != UNSELECTED else "", record.get("human_core_literacy_candidates") or [])
    return {
        "edit_bloom": bloom,
        "edit_primary": primary,
        "edit_candidates": cands,
        "edit_comment_bloom": record.get("human_comment_bloom", "") or "",
        "edit_comment_core": record.get("human_comment_core", "") or "",
    }


def current_time_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def set_flash(msg: str, level: str = "info") -> None:
    st.session_state["flash_message"] = msg
    st.session_state["flash_level"] = level


def show_flash() -> None:
    msg = st.session_state.get("flash_message")
    if not msg:
        return
    level = st.session_state.get("flash_level", "info")
    if level == "success":
        st.success(msg)
    elif level == "warning":
        st.warning(msg)
    else:
        st.info(msg)
    st.session_state["flash_message"] = ""


def build_draft_payload(task_key: str, record_uid: str) -> Dict[str, Any]:
    primary = st.session_state.get("edit_primary", UNSELECTED)
    primary_value = primary if primary in CORE_LITERACIES else ""
    selected_bloom = st.session_state.get("edit_bloom", [])
    selected_bloom = [x for x in selected_bloom if x in BLOOM_LEVELS and x != UNSELECTED]
    return {
        "record_uid": record_uid,
        "human_bloom_level": selected_bloom,
        "human_core_literacy_primary": primary_value,
        "human_core_literacy_candidates": sanitize_candidates(primary_value, st.session_state.get("edit_candidates", [])),
        "human_comment_bloom": st.session_state.get("edit_comment_bloom", "").strip(),
        "human_comment_core": st.session_state.get("edit_comment_core", "").strip(),
        "human_annotator": task_key,
        "draft_updated_at": current_time_str(),
    }


def draft_has_content(payload: Dict[str, Any]) -> bool:
    return bool(payload.get("human_bloom_level")) or bool(payload.get("human_core_literacy_primary")) or bool(payload.get("human_core_literacy_candidates")) or bool(payload.get("human_comment_bloom")) or bool(payload.get("human_comment_core"))


def persist_draft(task_key: str, record_uid: str) -> None:
    drafts_key = f"drafts::{task_key}"
    drafts = deepcopy(st.session_state[drafts_key])
    payload = build_draft_payload(task_key, record_uid)
    if draft_has_content(payload):
        drafts[record_uid] = payload
    else:
        drafts.pop(record_uid, None)
    if drafts != st.session_state[drafts_key]:
        st.session_state[drafts_key] = drafts


def persist_save(task_key: str, record_uid: str):
    saved_key = f"saved::{task_key}"
    drafts_key = f"drafts::{task_key}"
    saved = deepcopy(st.session_state[saved_key])
    drafts = deepcopy(st.session_state[drafts_key])

    payload = build_draft_payload(task_key, record_uid)
    if not payload.get("human_bloom_level") or not payload.get("human_core_literacy_primary"):
        return False, "请至少选择 Bloom 层级和核心素养主标签后再保存。"

    payload["human_updated_at"] = current_time_str()
    payload["human_status"] = "已标注"

    saved[record_uid] = payload
    drafts.pop(record_uid, None)

    st.session_state[saved_key] = saved
    st.session_state[drafts_key] = drafts
    st.session_state["last_save_msg"] = f"已保存：{record_uid}（{payload['human_updated_at']}）"
    return True, st.session_state["last_save_msg"]


def export_saved_rows(task_key: str) -> List[Dict[str, Any]]:
    saved = st.session_state[f"saved::{task_key}"]
    rows: List[Dict[str, Any]] = []
    for uid, rec in saved.items():
        if not rec.get("human_bloom_level") or not rec.get("human_core_literacy_primary"):
            continue
        rows.append({
            "id": uid,
            "human_bloom_level": rec.get("human_bloom_level", ""),
            "human_core_literacy_primary": rec.get("human_core_literacy_primary", ""),
            "human_core_literacy_candidates": rec.get("human_core_literacy_candidates", []),
            "human_comment_bloom": rec.get("human_comment_bloom", ""),
            "human_comment_core": rec.get("human_comment_core", ""),
            "human_annotator": rec.get("human_annotator", ""),
            "human_updated_at": rec.get("human_updated_at", ""),
            "human_status": rec.get("human_status", "已标注"),
        })
    rows.sort(key=lambda x: str(x.get("id", "")))
    return rows


def export_saved_results_json(task_key: str) -> bytes:
    return json.dumps(export_saved_rows(task_key), ensure_ascii=False, indent=2).encode("utf-8")


def export_saved_results_csv(task_key: str) -> bytes:
    rows = export_saved_rows(task_key)
    output = io.StringIO()
    fieldnames = [
        "id", "human_bloom_level", "human_core_literacy_primary", "human_core_literacy_candidates",
        "human_comment_bloom", "human_comment_core", "human_annotator", "human_updated_at", "human_status",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        row = dict(row)
        row["human_core_literacy_candidates"] = "、".join(row.get("human_core_literacy_candidates", []))
        row["human_bloom_level"] = "、".join(row.get("human_bloom_level", []))
        writer.writerow(row)
    return output.getvalue().encode("utf-8-sig")


def export_progress_bundle(task_key: str) -> bytes:
    payload = {
        "tool": "annotation_tool",
        "version": 2,
        "task": task_key,
        "exported_at": current_time_str(),
        "current_index": st.session_state.get(f"index::{task_key}", 0),
        "saved": st.session_state.get(f"saved::{task_key}", {}),
        "drafts": st.session_state.get(f"drafts::{task_key}", {}),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def import_progress_file(task_key: str, uploaded_file, total: int) -> tuple[bool, str]:
    try:
        data = json.loads(uploaded_file.getvalue().decode("utf-8"))
    except Exception as e:
        return False, f"导入失败：文件不是合法 JSON。{e}"

    saved: Dict[str, Dict[str, Any]] = {}
    drafts: Dict[str, Dict[str, Any]] = {}
    current_index = 0

    if isinstance(data, list):
        for i, rec in enumerate(data):
            if isinstance(rec, dict):
                uid = str(rec.get("id") or rec.get("record_uid") or f"item_{i+1}")
                saved[uid] = rec
    elif isinstance(data, dict):
        task_in_file = data.get("task")
        if task_in_file and task_in_file != task_key:
            return False, f"导入失败：该文件属于 {task_in_file}，当前任务是 {task_key}。"
        raw_saved = data.get("saved", data.get("annotations", {}))
        raw_drafts = data.get("drafts", {})
        if isinstance(raw_saved, list):
            for i, rec in enumerate(raw_saved):
                if isinstance(rec, dict):
                    uid = str(rec.get("id") or rec.get("record_uid") or f"item_{i+1}")
                    saved[uid] = rec
        elif isinstance(raw_saved, dict):
            saved = raw_saved
        if isinstance(raw_drafts, dict):
            drafts = raw_drafts
        current_index = int(data.get("current_index", 0) or 0)
    else:
        return False, "导入失败：不支持的 JSON 结构。"

    st.session_state[f"saved::{task_key}"] = saved
    st.session_state[f"drafts::{task_key}"] = drafts
    st.session_state[f"index::{task_key}"] = max(0, min(current_index, max(total - 1, 0)))
    st.session_state["editor_synced_for"] = None
    return True, f"导入成功：已恢复 {len(saved)} 道已保存题、{len(drafts)} 道草稿。"


def init_task_data(task_key: str) -> None:
    base_key = f"base::{task_key}"
    saved_key = f"saved::{task_key}"
    drafts_key = f"drafts::{task_key}"
    idx_key = f"index::{task_key}"

    if base_key not in st.session_state:
        st.session_state[base_key] = load_base_records(task_key)
    if saved_key not in st.session_state:
        st.session_state[saved_key] = load_saved_annotations(task_key)
    if drafts_key not in st.session_state:
        st.session_state[drafts_key] = load_drafts(task_key)
    if idx_key not in st.session_state:
        st.session_state[idx_key] = 0


def get_active_task() -> str:
    q = st.query_params.get("task", "teacher1")
    if isinstance(q, list):
        q = q[0] if q else "teacher1"
    return q if q in TASKS else "teacher1"


# def switch_task(task_key: str) -> None:
#     st.query_params["task"] = task_key
#     st.session_state["active_task"] = task_key
#     st.session_state["editor_synced_for"] = None


def sync_editor_if_needed(task_key: str, record_uid: str, working_record: Dict[str, Any]) -> None:
    marker = f"{task_key}::{record_uid}"
    if st.session_state.get("editor_synced_for") == marker:
        return
    state = build_editor_state(working_record)
    for k, v in state.items():
        st.session_state[k] = v
    st.session_state["editor_synced_for"] = marker


def go_to_index(task_key: str, idx: int) -> None:
    total = len(st.session_state[f"base::{task_key}"])
    idx = max(0, min(idx, total - 1)) if total else 0
    st.session_state[f"index::{task_key}"] = idx
    st.session_state["editor_synced_for"] = None


def save_current_draft_before_move(task_key: str, record_uid: str) -> None:
    persist_draft(task_key, record_uid)


# =========================
# 页面主体
# =========================
active_task = get_active_task()
init_task_data(active_task)
st.session_state.setdefault("active_task", active_task)
st.session_state.setdefault("editor_synced_for", None)
st.session_state.setdefault("last_save_msg", "")
st.session_state.setdefault("flash_message", "")
st.session_state.setdefault("flash_level", "info")

if st.session_state.get("active_task") != active_task:
    st.session_state["active_task"] = active_task
    st.session_state["editor_synced_for"] = None

base_records = st.session_state[f"base::{active_task}"]
saved_map = st.session_state[f"saved::{active_task}"]
drafts_map = st.session_state[f"drafts::{active_task}"]
current_index = st.session_state[f"index::{active_task}"]

if not base_records:
    st.warning("当前任务数据为空。")
    st.stop()

current_record = base_records[current_index]
current_uid = get_record_uid(current_record, current_index)
working_record = build_working_record(current_record, saved_map.get(current_uid), drafts_map.get(current_uid))
sync_editor_if_needed(active_task, current_uid, working_record)

# 轻量级实时草稿保存：仅保存在当前会话内，刷新后需依靠导入文件恢复
persist_draft(active_task, current_uid)
drafts_map = st.session_state[f"drafts::{active_task}"]

st.title("数字题人工标注工具")
show_flash()
total_count = len(base_records)
current_no = current_index + 1

st.markdown(
    f"""
    <div style="
        display: inline-block;
        padding: 10px 18px;
        margin: 10px 0 18px 0;
        border-radius: 14px;
        background: #f8fbff;
        border: 1px solid #dbeafe;
        font-size: 30px;
        font-weight: 800;
        color: #1d4ed8;
    ">
        第 {current_no} / {total_count} 题
    </div>
    """,
    unsafe_allow_html=True,
)
with st.sidebar:

    st.subheader("标注进度")
    st.markdown(f"**当前任务：{TASKS[active_task]['label']}**")

    total = len(base_records)
    saved_count = sum(record_is_saved(get_record_uid(r, i), saved_map) for i, r in enumerate(base_records))
    draft_count = sum(get_draft_status(get_record_uid(r, i), drafts_map) for i, r in enumerate(base_records))
    st.divider()
    st.metric("总题数", total)
    st.metric("已保存", saved_count)
    st.metric("草稿题数", draft_count)
    st.metric("未保存", total - saved_count)
    st.progress(saved_count / total if total else 0)
    if st.session_state.get("last_save_msg"):
        st.caption(st.session_state["last_save_msg"])
    st.caption("说明：当前页会自动存为会话草稿；想跨刷新/跨电脑继续，请下载进度文件。")

    st.divider()
    
    uploaded_progress = st.file_uploader(
    "导入进度 JSON",
    type=["json"],
    key=f"importer::{active_task}",
    help="支持导入之前下载的“当前进度备份 JSON”或“已保存结果 JSON”。",
    )

    import_marker_key = f"imported_file_marker::{active_task}"
    
    if uploaded_progress is not None:
        file_bytes = uploaded_progress.getvalue()
        current_marker = (uploaded_progress.name, len(file_bytes), hash(file_bytes))
    
        if st.session_state.get(import_marker_key) != current_marker:
            ok, msg = import_progress_file(active_task, uploaded_progress, total)
            st.session_state[import_marker_key] = current_marker
            set_flash(msg, "success" if ok else "warning")
            st.rerun()
    else:
        st.session_state[import_marker_key] = None

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button(
            "下载当前进度",
            data=export_progress_bundle(active_task),
            file_name=f"{active_task}_progress_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )
    with col_dl2:
        st.download_button(
            "下载结果 JSON",
            data=export_saved_results_json(active_task),
            file_name=f"{active_task}_saved_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )

    st.download_button(
        "下载结果 CSV",
        data=export_saved_results_csv(active_task),
        file_name=f"{active_task}_saved_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    if st.button("清空当前任务进度", type="secondary", use_container_width=True):
        st.session_state[f"saved::{active_task}"] = {}
        st.session_state[f"drafts::{active_task}"] = {}
        st.session_state[f"index::{active_task}"] = 0
        st.session_state["editor_synced_for"] = None
        set_flash("已清空当前任务的会话进度。", "success")
        st.rerun()

    st.divider()
    only_unfinished = st.checkbox("只看未保存题", value=False)
    title_map: Dict[str, int] = {}
    for i, rec in enumerate(base_records):
        uid = get_record_uid(rec, i)
        is_saved = record_is_saved(uid, saved_map)
        has_draft = get_draft_status(uid, drafts_map)
        if only_unfinished and is_saved:
            continue
        if is_saved:
            status = "✅"
        elif has_draft:
            status = "📝"
        else:
            status = "⬜"
        title = f"{status} 第{i + 1}题 · {uid}"
        title_map[title] = i

    current_title = next((t for t, i in title_map.items() if i == current_index), list(title_map.keys())[0])
    selected_title = st.selectbox("题目列表", list(title_map.keys()), index=list(title_map.keys()).index(current_title))
    selected_index = title_map[selected_title]
    if selected_index != current_index:
        save_current_draft_before_move(active_task, current_uid)
        go_to_index(active_task, selected_index)
        st.rerun()

    if st.button("跳到下一道未保存题", use_container_width=True):
        targets = [i for i in range(total) if not record_is_saved(get_record_uid(base_records[i], i), saved_map)]
        if targets:
            nxt = next((i for i in targets if i > current_index), targets[0])
            save_current_draft_before_move(active_task, current_uid)
            go_to_index(active_task, nxt)
            st.rerun()

all_done = saved_count == total
status_note = "已全部完成，可直接下载结果。" if all_done else "未全部完成，可先下载当前进度，之后再导入继续。"
st.markdown(
    f'<div class="status-line">当前任务：{TASKS[active_task]["label"]} · 第 {current_index + 1} / {len(base_records)} 题 · {status_note}</div>',
    unsafe_allow_html=True,
)

left, right = st.columns([1.72, 1], gap="large")

with left:
    st.markdown("## 题目区")
    with st.container(height=1000, border=True):
        st.markdown(f"**题目ID：** `{current_uid}`")
        type_text = current_record.get("type") or ""
        st.markdown(f"**题型：** {type_text}")
        if current_record.get("difficulty"):
            st.markdown(f"**难度：** {current_record['difficulty']}")
        if current_record.get("grades"):
            st.markdown(f"**年级：** {'、'.join(current_record['grades'])}")
        if current_record.get("score") not in [None, ""]:
            st.markdown(f"**分值：** {current_record['score']}")
        if current_record.get("knowledges"):
            st.markdown(f"**知识点：** {'、'.join(current_record['knowledges'])}")
        if current_record.get("abilities"):
            st.markdown(f"**能力要求：** {'、'.join(current_record['abilities'])}")

        st.markdown("### 题干")
        render_text_block(current_record.get("normalized_stem") or current_record.get("stem"))
        if current_record.get("stem_images"):
            st.markdown("### 题干图片")
            render_images(current_record.get("stem_images", []))

        if current_record.get("options"):
            st.markdown("### 选项")
            render_options(current_record.get("options", []))

        st.markdown("### 参考答案")
        render_text_block(current_record.get("answer"), compact=True)

        st.markdown("### 解析")
        render_text_block(current_record.get("normalized_analysis") or current_record.get("analysis"))
        if current_record.get("analysis_images"):
            st.markdown("### 解析图片")
            render_images(current_record.get("analysis_images", []))

with right:
    bloom_model = current_record.get("bloom_level") or "无"
    bloom_reason = current_record.get("bloom_reason") or ""
    core_model = current_record.get("core_literacy_primary") or "无"
    core_candidates = current_record.get("core_literacy_candidates") or []
    core_reason = current_record.get("core_literacy_reason") or ""

    with st.container(border=True):
        st.markdown("### Bloom 标注")

        st.markdown(
            f"""
<div class="model-card">
  <div class="model-title">Bloom 模型建议</div>
  <div class="model-row"><b>建议层级：</b>{escape_html(str(bloom_model))}</div>
  <div class="model-row"><b>建议理由：</b>{escape_html(str(bloom_reason or '无'))}</div>
</div>
""",
            unsafe_allow_html=True,
        )

        st.caption("Bloom 层级")
        st.multiselect(
            "Bloom 层级",
            options=BLOOM_LEVELS[1:],   # 一般不建议把“未选择”放进多选
            key="edit_bloom",
            placeholder="可选择多个 Bloom 层级",
            
        )
        st.text_area("Bloom 备注", key="edit_comment_bloom", height=88, placeholder="可选")

    st.write("")

    with st.container(border=True):
        st.markdown("### 核心素养标注")

        st.markdown(
            f"""
<div class="model-card">
  <div class="model-title">核心素养模型建议</div>
  <div class="model-row"><b>主标签：</b>{escape_html(str(core_model))}</div>
  <div class="model-row"><b>候选：</b>{escape_html('、'.join(core_candidates) if core_candidates else '无')}</div>
  <div class="model-row"><b>建议理由：</b>{escape_html(str(core_reason or '无'))}</div>
</div>
""",
            unsafe_allow_html=True,
        )

        st.selectbox("核心素养主标签", options=PRIMARY_OPTIONS, key="edit_primary")
        st.multiselect(
            "核心素养候选（最多 3 个）",
            options=CORE_LITERACIES,
            key="edit_candidates",
            max_selections=3,
            help="若选择了主标签，保存时会自动保证主标签出现在候选首位。",
        )
        st.text_area("核心素养备注", key="edit_comment_core", height=88, placeholder="可选")

    st.write("")
    nav1, nav2 = st.columns(2)
    with nav1:
        if st.button("⬅ 上一题", disabled=(current_index == 0), use_container_width=True):
            save_current_draft_before_move(active_task, current_uid)
            go_to_index(active_task, current_index - 1)
            st.rerun()
    with nav2:
        if st.button("下一题 ➡", disabled=(current_index == len(base_records) - 1), use_container_width=True):
            save_current_draft_before_move(active_task, current_uid)
            go_to_index(active_task, current_index + 1)
            st.rerun()

    st.write("")
    save1, save2 = st.columns(2)
    with save1:
        if st.button("保存当前题", use_container_width=True):
            ok, msg = persist_save(active_task, current_uid)
            set_flash(msg, "success" if ok else "warning")
            st.rerun()
    with save2:
        if st.button("保存并下一题", type="primary", use_container_width=True):
            ok, msg = persist_save(active_task, current_uid)
            if ok:
                set_flash(msg, "success")
                if current_index < len(base_records) - 1:
                    go_to_index(active_task, current_index + 1)
            else:
                set_flash(msg, "warning")
            st.rerun()
