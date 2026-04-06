import html
import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import streamlit as st

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

# 这里直接配置三位老师/三份数据文件
TASKS: Dict[str, Dict[str, str]] = {
    "teacher1": {"label": "教师 1", "data_file": "teacher_1.json"},
    "teacher2": {"label": "教师 2", "data_file": "teacher_2.json"},
    "teacher3": {"label": "教师 3", "data_file": "teacher_3.json"},
}

BASE_DIR = Path(__file__).parent
ASSET_DIRS = [BASE_DIR, BASE_DIR / "data", BASE_DIR / "images"]

# =========================
# 样式
# =========================
st.markdown(
    """
<style>
.block-container {
    padding-top: 1.0rem;
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
.task-link-box {
    border: 1px dashed #cbd5e1;
    background: #f8fafc;
    border-radius: 12px;
    padding: 10px 12px;
    font-size: 0.92rem;
}
.saved-badge { color: #15803d; font-weight: 700; }
.draft-badge { color: #b45309; font-weight: 700; }
.empty-badge { color: #64748b; font-weight: 700; }
</style>
""",
    unsafe_allow_html=True,
)


# =========================
# 文件读写
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


def write_json_file(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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


def get_saved_file(task_key: str) -> Path:
    return BASE_DIR / "outputs" / f"{task_key}_saved.json"


def get_draft_file(task_key: str) -> Path:
    return BASE_DIR / "outputs" / f"{task_key}_drafts.json"


# =========================
# 文本与公式渲染
# =========================
def normalize_text(text: Any) -> str:
    s = "" if text is None else str(text)
    s = s.replace("\u00a0", " ")
    s = s.replace("\\left", "").replace("\\right", "")
    s = s.replace("\\qquad", " ").replace("\\quad", " ")
    s = s.replace("\\;", " ").replace("\\,", " ").replace("\\!", "")
    s = s.replace("\\displaystyle", "")
    s = s.replace("\\mathrm", "")
    s = s.replace("\\text", "")
    s = s.replace("\\operatorname", "")
    s = s.replace("\\cdot", "·")
    s = s.replace("\\times", "×")
    s = s.replace("\\div", "÷")
    s = s.replace("\\pm", "±")
    s = s.replace("\\mp", "∓")
    s = s.replace("\\leqslant", "≤").replace("\\leq", "≤")
    s = s.replace("\\geqslant", "≥").replace("\\geq", "≥")
    s = s.replace("\\neq", "≠")
    s = s.replace("\\approx", "≈")
    s = s.replace("\\because", "∵")
    s = s.replace("\\therefore", "∴")
    s = s.replace("\\angle", "∠")
    s = s.replace("\\triangle", "△")
    s = s.replace("\\parallel", "∥")
    s = s.replace("\\perp", "⟂")
    s = s.replace("\\circ", "°")
    s = s.replace("^^{°}", "°").replace("^^{\\circ}", "°")
    s = s.replace("^{°}", "°").replace("^{\\circ}", "°")
    s = s.replace("{°}", "°")
    s = s.replace("\\ldots", "…").replace("\\cdots", "…")
    s = s.replace("\\%", "%")
    s = s.replace("\\(", "").replace("\\)", "")
    s = s.replace("\\[", "").replace("\\]", "")
    s = s.replace("$", "")

    greek_map = {
        r"\\alpha": "α", r"\\beta": "β", r"\\gamma": "γ", r"\\theta": "θ",
        r"\\lambda": "λ", r"\\mu": "μ", r"\\pi": "π", r"\\rho": "ρ",
        r"\\sigma": "σ", r"\\phi": "φ", r"\\omega": "ω",
    }
    for k, v in greek_map.items():
        s = re.sub(k + r"(?![A-Za-z])", v, s)

    s = re.sub(r"\\begin\{array\}\{[^}]*\}", "\\begin{cases}", s)
    s = s.replace("\\end{array}", "\\end{cases}")
    s = re.sub(r"\{\s*\\circ\s*\}", "°", s)
    s = re.sub(r"\^\^+", "^", s)
    s = re.sub(r"\s+", " ", s)
    s = s.replace(" \\n", "\\n").replace("\\n ", "\\n")
    return s.strip()


def escape_html(text: str) -> str:
    return html.escape(text, quote=False)


def find_matching_brace(s: str, start: int) -> int:
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def read_group(s: str, i: int):
    if i >= len(s):
        return "", i
    if s[i] == "{":
        end = find_matching_brace(s, i)
        if end != -1:
            return s[i + 1:end], end + 1
    return s[i], i + 1


def render_formula_html(text: str) -> str:
    s = normalize_text(text)

    def parse(expr: str) -> str:
        out: List[str] = []
        i = 0
        while i < len(expr):
            if expr.startswith("\\frac", i):
                num, p1 = read_group(expr, i + 5)
                den, p2 = read_group(expr, p1)
                out.append(f'<span class="frac"><span>{parse(num)}</span><span>{parse(den)}</span></span>')
                i = p2
                continue
            if expr.startswith("\\sqrt", i):
                body, p1 = read_group(expr, i + 5)
                out.append(f'<span class="sqrt"><span class="sqrt-sign">√</span><span class="sqrt-body">{parse(body)}</span></span>')
                i = p1
                continue
            if expr.startswith("\\overset", i):
                top, p1 = read_group(expr, i + 8)
                base, p2 = read_group(expr, p1)
                out.append(f'<span class="overset"><span class="overset-top">{parse(top)}</span><span class="overset-base">{parse(base)}</span></span>')
                i = p2
                continue
            if expr.startswith("\\begin{cases}", i):
                end = expr.find("\\end{cases}", i)
                if end != -1:
                    body = expr[i + len("\\begin{cases}"):end]
                    lines = [x.strip() for x in re.split(r"\\\\", body) if x.strip()]
                    line_html = "".join(f'<div class="formula-line">{parse(line)}</div>' for line in lines)
                    out.append(f'<span class="cases"><span class="cases-brace">{{</span><span class="cases-lines">{line_html}</span></span>')
                    i = end + len("\\end{cases}")
                    continue
            ch = expr[i]
            if ch == "^":
                grp, ni = read_group(expr, i + 1)
                out.append(f"<sup>{parse(grp)}</sup>")
                i = ni
                continue
            if ch == "_":
                grp, ni = read_group(expr, i + 1)
                g = grp.strip()
                if len(g) >= 3 and set(g) <= {"_"}:
                    out.append('<span class="placeholder-line"></span>')
                else:
                    out.append(f"<sub>{parse(grp)}</sub>")
                i = ni
                continue
            if expr.startswith("\\\\", i):
                out.append('<span class="sep-line"></span>')
                i += 2
                continue
            if ch in "{}":
                i += 1
                continue
            out.append(escape_html(ch))
            i += 1
        joined = "".join(out)
        joined = joined.replace("-", "−")
        return joined

    html_text = parse(s)
    html_text = re.sub(r"\s{2,}", " ", html_text)
    return html_text


def render_text_block(text: Any, compact: bool = False) -> None:
    raw = "" if text is None else str(text)
    normalized = normalize_text(raw)
    lines = [x.strip() for x in normalized.split("\n") if x.strip()]
    if not lines:
        st.markdown('<div class="small-muted">暂无内容</div>', unsafe_allow_html=True)
        return
    css_class = "math-text compact" if compact else "math-text"
    html_parts = [f'<div class="{css_class}">' + render_formula_html(line) + '</div>' for line in lines]
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_options(options: List[Dict[str, Any]]) -> None:
    if not options:
        return
    blocks: List[str] = []
    for opt in options:
        label = escape_html(str(opt.get("index", "")))
        text_html = render_formula_html(str(opt.get("text", "")))
        blocks.append(
            f'<div class="option-card"><div class="option-label">{label}</div><div class="math-text compact">{text_html}</div></div>'
        )
    st.markdown("".join(blocks), unsafe_allow_html=True)
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
    path = get_saved_file(task_key)
    if not path.exists():
        return {}
    data = read_json_file(path)
    if isinstance(data, list):
        out = {}
        for i, r in enumerate(data):
            out[get_record_uid(r, i)] = r
        return out
    if isinstance(data, dict):
        return data
    return {}


def load_drafts(task_key: str) -> Dict[str, Dict[str, Any]]:
    path = get_draft_file(task_key)
    if not path.exists():
        return {}
    data = read_json_file(path)
    return data if isinstance(data, dict) else {}


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
    bloom = record.get("human_bloom_level") or UNSELECTED
    primary = record.get("human_core_literacy_primary") or UNSELECTED
    if bloom not in BLOOM_LEVELS:
        bloom = UNSELECTED
    if primary not in PRIMARY_OPTIONS:
        primary = UNSELECTED
    cands = sanitize_candidates(
        primary if primary in CORE_LITERACIES else "",
        record.get("human_core_literacy_candidates") or [],
    )
    return {
        "edit_bloom": bloom,
        "edit_primary": primary,
        "edit_candidates": cands,
        "edit_comment_bloom": record.get("human_comment_bloom", ""),
        "edit_comment_core": record.get("human_comment_core", ""),
    }


def current_time_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def build_draft_payload(task_key: str, record_uid: str) -> Dict[str, Any]:
    primary = st.session_state.get("edit_primary", UNSELECTED)
    primary_value = primary if primary in CORE_LITERACIES else ""
    return {
        "record_uid": record_uid,
        "human_bloom_level": "" if st.session_state.get("edit_bloom") == UNSELECTED else st.session_state.get("edit_bloom", ""),
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
        write_json_file(get_draft_file(task_key), drafts)


def persist_save(task_key: str, record_uid: str) -> None:
    saved_key = f"saved::{task_key}"
    drafts_key = f"drafts::{task_key}"
    saved = deepcopy(st.session_state[saved_key])
    drafts = deepcopy(st.session_state[drafts_key])

    payload = build_draft_payload(task_key, record_uid)
    payload["human_updated_at"] = current_time_str()
    payload["human_status"] = "已标注" if payload.get("human_bloom_level") and payload.get("human_core_literacy_primary") else "未完成"

    saved[record_uid] = payload
    drafts.pop(record_uid, None)

    st.session_state[saved_key] = saved
    st.session_state[drafts_key] = drafts
    write_json_file(get_saved_file(task_key), saved)
    write_json_file(get_draft_file(task_key), drafts)
    st.session_state["last_save_msg"] = f"已保存：{record_uid}（{payload['human_updated_at']}）"


def export_merged_records(task_key: str) -> bytes:
    base = st.session_state[f"base::{task_key}"]
    saved = st.session_state[f"saved::{task_key}"]
    merged: List[Dict[str, Any]] = []
    for i, rec in enumerate(base):
        uid = get_record_uid(rec, i)
        item = deepcopy(rec)
        if uid in saved:
            item.update(saved[uid])
        merged.append(item)
    return json.dumps(merged, ensure_ascii=False, indent=2).encode("utf-8")


def build_task_url(task_key: str) -> str:
    params = dict(st.query_params)
    params["task"] = task_key
    return "?" + urlencode(params, doseq=True)


# =========================
# 会话初始化
# =========================
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


def switch_task(task_key: str) -> None:
    st.query_params["task"] = task_key
    st.session_state["active_task"] = task_key
    st.session_state["editor_synced_for"] = None


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

# 轻量级实时草稿保存：仅在值变化后的 rerun 时更新，不打断用户
persist_draft(active_task, current_uid)
drafts_map = st.session_state[f"drafts::{active_task}"]

st.title("数字题人工标注工具")

with st.sidebar:
    st.subheader("任务入口")
    labels = [f"{TASKS[k]['label']} · {k}" for k in TASKS]
    keys = list(TASKS.keys())
    current_radio = keys.index(active_task)
    chosen_label = st.radio("选择老师任务", labels, index=current_radio, label_visibility="collapsed")
    chosen_key = keys[labels.index(chosen_label)]
    if chosen_key != active_task:
        save_current_draft_before_move(active_task, current_uid)
        switch_task(chosen_key)
        st.rerun()

    st.markdown('<div class="task-link-box">', unsafe_allow_html=True)
    st.markdown("**三个直达链接**")
    for k in keys:
        st.markdown(f"- `{build_task_url(k)}`")
    st.markdown("</div>", unsafe_allow_html=True)

    total = len(base_records)
    saved_count = sum(record_is_saved(get_record_uid(r, i), saved_map) for i, r in enumerate(base_records))
    draft_only_count = sum(
        (not record_is_saved(get_record_uid(r, i), saved_map)) and get_draft_status(get_record_uid(r, i), drafts_map)
        for i, r in enumerate(base_records)
    )

    st.divider()
    st.metric("总题数", total)
    st.metric("已保存", saved_count)
    st.metric("暂存未保存", draft_only_count)
    st.progress(saved_count / total if total else 0)
    if st.session_state.get("last_save_msg"):
        st.caption(st.session_state["last_save_msg"])

    st.divider()
    only_unfinished = st.checkbox("只看未保存题", value=False)
    visible_indices: List[int] = []
    title_map: Dict[str, int] = {}
    for i, rec in enumerate(base_records):
        uid = get_record_uid(rec, i)
        is_saved = record_is_saved(uid, saved_map)
        has_draft = get_draft_status(uid, drafts_map)
        if only_unfinished and is_saved:
            continue
        status = "✅" if is_saved else ("📝" if has_draft else "⬜")
        title = f"{status} 第{i + 1}题 · {uid}"
        visible_indices.append(i)
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

    st.divider()
    st.download_button(
        "下载已保存结果 JSON",
        data=export_merged_records(active_task),
        file_name=f"{active_task}_annotations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        use_container_width=True,
    )

# 顶部导航
nav1, nav2, nav3, nav4 = st.columns([1, 1, 1.15, 1.2])
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
with nav3:
    if st.button("保存并下一题", type="primary", use_container_width=True):
        persist_save(active_task, current_uid)
        if current_index < len(base_records) - 1:
            go_to_index(active_task, current_index + 1)
        st.rerun()
with nav4:
    status_html = '<span class="saved-badge">已保存</span>' if record_is_saved(current_uid, saved_map) else (
        '<span class="draft-badge">暂存未保存</span>' if get_draft_status(current_uid, drafts_map) else '<span class="empty-badge">未开始</span>'
    )
    st.markdown(f"第 **{current_index + 1} / {len(base_records)}** 题 · {status_html}", unsafe_allow_html=True)

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
    with st.container(border=True):
        bloom_model = current_record.get("bloom_level") or "无"
        bloom_reason = current_record.get("bloom_reason") or ""
        core_model = current_record.get("core_literacy_primary") or "无"
        core_candidates = current_record.get("core_literacy_candidates") or []
        core_reason = current_record.get("core_literacy_reason") or ""
        st.markdown(
            f"""
<div class="model-card">
  <div class="model-title">模型建议</div>
  <div class="model-row"><b>Bloom：</b>{escape_html(str(bloom_model))}</div>
  <div class="model-row"><b>Bloom 理由：</b>{escape_html(str(bloom_reason or '无'))}</div>
  <div class="model-row"><b>核心素养主标签：</b>{escape_html(str(core_model))}</div>
  <div class="model-row"><b>核心素养候选：</b>{escape_html('、'.join(core_candidates) if core_candidates else '无')}</div>
  <div class="model-row"><b>核心素养理由：</b>{escape_html(str(core_reason or '无'))}</div>
</div>
""",
            unsafe_allow_html=True,
        )

    st.write("")

    with st.container(border=True):
        st.markdown("### Bloom 标注")
        st.radio(
            "Bloom 层级",
            options=BLOOM_LEVELS,
            key="edit_bloom",
            horizontal=True,
            label_visibility="collapsed",
        )
        st.text_area("Bloom 备注", key="edit_comment_bloom", height=88, placeholder="可选")

    st.write("")

    with st.container(border=True):
        st.markdown("### 核心素养标注")
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
    b1, b2 = st.columns(2)
    with b1:
        if st.button("保存当前题", use_container_width=True):
            persist_save(active_task, current_uid)
            st.rerun()
    with b2:
        if st.button("仅暂存草稿", use_container_width=True):
            persist_draft(active_task, current_uid)
            st.session_state["last_save_msg"] = f"已暂存：{current_uid}（{current_time_str()}）"
            st.rerun()
