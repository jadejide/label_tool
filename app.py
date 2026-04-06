import json
import html
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

st.set_page_config(page_title="数字题人工标注工具", layout="wide")

# =========================
# 基础配置
# =========================
UNSELECTED = "未选择"
BLOOM_LEVELS = [UNSELECTED, "记忆", "理解", "应用", "分析", "评价", "创造"]
CORE_LITERACIES = [
    "抽象能力", "运算能力", "几何直观", "空间观念", "推理能力",
    "数据观念", "模型观念", "应用意识", "创新意识",
]
PRIMARY_OPTIONS = [UNSELECTED] + CORE_LITERACIES
TASK_MAP = {
    "teacher1": {"label": "teacher1", "file": "data/teacher1.json"},
    "teacher2": {"label": "teacher2", "file": "data/teacher2.json"},
    "teacher3": {"label": "teacher3", "file": "data/teacher3.json"},
}

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

# =========================
# 全局样式
# =========================
st.markdown(
    """
<style>
.block-container {
    padding-top: 1.05rem;
    padding-bottom: 1.8rem;
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
.small-muted {
    color: #667085;
    font-size: 0.92rem;
}
.status-line {
    font-size: 0.92rem;
    color: #667085;
    margin-top: -0.2rem;
    margin-bottom: 0.6rem;
}
.model-card {
    border: 1px solid #dbeafe;
    background: #f8fbff;
    border-radius: 14px;
    padding: 12px 14px;
}
.model-row {
    margin: 0.25rem 0;
}
.math-text {
    font-size: 20px;
    line-height: 1.95;
    word-break: break-word;
    white-space: normal;
}
.math-text.compact {
    font-size: 18px;
    line-height: 1.8;
}
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
.formula-line {
    white-space: nowrap;
}
.placeholder-line {
    display: inline-block;
    min-width: 4.8em;
    border-bottom: 1.6px solid #64748b;
    transform: translateY(-0.08em);
}
.sep-line {
    display: block;
    height: 10px;
}
.math-bold { font-weight: 700; }
.sqrt { display: inline-flex; align-items: flex-start; white-space: nowrap; vertical-align: middle; }
.sqrt-sign { font-size: 1.08em; line-height: 1; padding-right: 1px; }
.sqrt-body { border-top: 1.5px solid currentColor; padding: 0 2px 0 3px; line-height: 1.2; }
.overset { display: inline-flex; flex-direction: column; align-items: center; line-height: 1; vertical-align: middle; }
.overset-top { font-size: 0.7em; margin-bottom: 1px; }
.overset-base { line-height: 1; }
.overset-dot { display: inline-block; }
.empty-lite {
    color: #667085;
    font-size: 0.95rem;
}
</style>
""",
    unsafe_allow_html=True,
)


# =========================
# 文件读写
# =========================
def read_json_file(path: Path, default: Any):
    if not path.exists():
        return deepcopy(default)
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return deepcopy(default)
        return json.loads(text)
    except Exception:
        return deepcopy(default)



def write_json_atomic(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)



def load_json_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        st.error(f"未找到数据文件：{path}")
        st.stop()

    try:
        text = path.read_text(encoding="utf-8").strip()
    except Exception as e:
        st.error(f"读取数据文件失败：{path}\n{e}")
        st.stop()

    if not text:
        return []

    try:
        if path.suffix.lower() == ".jsonl":
            data = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            data = json.loads(text)
    except Exception as e:
        st.error(f"JSON 解析失败：{path}\n{e}")
        st.stop()

    if not isinstance(data, list):
        st.error("数据文件必须是 JSON 数组或 JSONL。")
        st.stop()
    return data



def dump_records_bytes(records: List[Dict[str, Any]]) -> bytes:
    return json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")



def get_saved_records_path(teacher_key: str) -> Path:
    return DATA_DIR / f"{teacher_key}_saved.json"



def get_drafts_path(teacher_key: str) -> Path:
    return DATA_DIR / f"{teacher_key}_drafts.json"



def get_legacy_autosave_path(teacher_key: str) -> Path:
    return DATA_DIR / f"{teacher_key}_autosave.json"



def load_saved_records_for_teacher(teacher_key: str) -> List[Dict[str, Any]]:
    saved_path = get_saved_records_path(teacher_key)
    legacy_path = get_legacy_autosave_path(teacher_key)
    original_path = BASE_DIR / TASK_MAP[teacher_key]["file"]
    if saved_path.exists():
        return load_json_records(saved_path)
    if legacy_path.exists():
        return load_json_records(legacy_path)
    return load_json_records(original_path)



def load_drafts_for_teacher(teacher_key: str) -> Dict[str, Any]:
    payload = read_json_file(get_drafts_path(teacher_key), default={})
    return payload if isinstance(payload, dict) else {}


# =========================
# 通用工具
# =========================
def current_time_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")



def get_query_teacher() -> str:
    teacher = st.query_params.get("teacher", "teacher1")
    if isinstance(teacher, list):
        teacher = teacher[0] if teacher else "teacher1"
    teacher = str(teacher).strip()
    return teacher if teacher in TASK_MAP else "teacher1"



def get_record_uid(record: Dict[str, Any], idx: int) -> str:
    return str(record.get("id") or record.get("sample_id") or f"item_{idx}")



def get_display_stem(record: Dict[str, Any]) -> str:
    return str(record.get("normalized_stem") or record.get("stem") or "")



def get_display_analysis(record: Dict[str, Any]) -> str:
    return str(record.get("normalized_analysis") or record.get("analysis") or "")



def ensure_candidates_include_primary(primary: str, candidates: List[str]) -> List[str]:
    clean: List[str] = []
    for item in candidates or []:
        if item in CORE_LITERACIES and item not in clean:
            clean.append(item)
    if primary in CORE_LITERACIES:
        if primary in clean:
            clean.remove(primary)
        clean = [primary] + clean
    return clean[:3]



def normalize_bloom(value: str) -> str:
    return value if value in BLOOM_LEVELS else UNSELECTED



def normalize_primary(value: str) -> str:
    return value if value in PRIMARY_OPTIONS else UNSELECTED



def normalize_annotation(annotation: Dict[str, Any]) -> Dict[str, Any]:
    bloom = normalize_bloom(str(annotation.get("human_bloom_level", "") or UNSELECTED))
    primary = normalize_primary(str(annotation.get("human_core_literacy_primary", "") or UNSELECTED))
    real_primary = primary if primary in CORE_LITERACIES else ""
    candidates = ensure_candidates_include_primary(real_primary, annotation.get("human_core_literacy_candidates", []) or [])
    return {
        "human_bloom_level": "" if bloom == UNSELECTED else bloom,
        "human_core_literacy_primary": real_primary,
        "human_core_literacy_candidates": candidates,
        "human_comment_bloom": str(annotation.get("human_comment_bloom", "")).strip(),
        "human_comment_core": str(annotation.get("human_comment_core", "")).strip(),
    }



def extract_saved_annotation(record: Dict[str, Any]) -> Dict[str, Any]:
    return normalize_annotation(
        {
            "human_bloom_level": record.get("human_bloom_level", ""),
            "human_core_literacy_primary": record.get("human_core_literacy_primary", ""),
            "human_core_literacy_candidates": record.get("human_core_literacy_candidates", []),
            "human_comment_bloom": record.get("human_comment_bloom", ""),
            "human_comment_core": record.get("human_comment_core", ""),
        }
    )



def build_annotation_from_widgets() -> Dict[str, Any]:
    return normalize_annotation(
        {
            "human_bloom_level": st.session_state.get("edit_bloom", UNSELECTED),
            "human_core_literacy_primary": st.session_state.get("edit_primary", UNSELECTED),
            "human_core_literacy_candidates": st.session_state.get("edit_candidates", []),
            "human_comment_bloom": st.session_state.get("edit_comment_bloom", ""),
            "human_comment_core": st.session_state.get("edit_comment_core", ""),
        }
    )



def current_is_done(record: Dict[str, Any]) -> bool:
    saved = extract_saved_annotation(record)
    return bool(saved["human_bloom_level"]) and bool(saved["human_core_literacy_primary"])



def draft_equals_saved(annotation: Dict[str, Any], record: Dict[str, Any]) -> bool:
    return normalize_annotation(annotation) == extract_saved_annotation(record)



def get_saved_status_text(record: Dict[str, Any]) -> str:
    return "已保存" if current_is_done(record) else "未保存"


# =========================
# 数学/富文本渲染
# 参考用户提供的 HTML 渲染思路，改写为 Python 版本
# =========================
KNOWN_CMD_MAP = {
    "pi": "π",
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "lambda": "λ",
    "mu": "μ",
    "theta": "θ",
    "vartriangle": "△",
    "triangle": "△",
    "bot": "⊥",
    "parallel": "∥",
    "angle": "∠",
}
TOKEN_CHAR_RE = re.compile(r"[A-Za-z0-9一-龥°△∠⊥∥+\-]")
TOKEN_CONT_RE = re.compile(r"[A-Za-z0-9.°△∠⊥∥+\-]")



def escape_html(text: Any) -> str:
    return html.escape(str(text or ""), quote=True)



def normalize_text(raw: Any) -> str:
    text = str(raw or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\u00A0\u200B-\u200D\uFEFF]", " ", text)
    text = re.sub(r"[\t\f\v]+", " ", text)
    text = text.replace("&nbsp;", " ")

    # 兼容这批题库里常见的脏命令和 OCR 残留
    text = re.sub(r"[≤⩽]\s*ft(?=[\(\[\{\|])", r"\\left", text)
    text = re.sub(r"[≥⩾]\s*ight(?=[\)\]\}\|\.])", r"\\right", text)
    text = re.sub(r"(?<![A-Za-z])sft(?=[0-9A-Za-z\(\{])", "sqrt", text)
    text = re.sub(r"\\?vartriangle\b", r"\\triangle", text)
    text = re.sub(r"\\?bot\b", r"\\bot", text)
    text = re.sub(r"\\?oversetbullet(?=[A-Za-z0-9一-龥])", r"\\oversetbullet", text)
    text = re.sub(r"\\?boldsymbol\b", r"\\boldsymbol", text)

    # 处理 array / cases 变体
    text = re.sub(
        r"\\left\\\{\\begin\{array\}\{[^}]*\}([\s\S]*?)\\end\{array\}\\right\.?",
        lambda m: f"\\begin{{cases}}{m.group(1)}\\end{{cases}}",
        text,
    )
    text = re.sub(
        r"\\left\\\{\\begin\{cases\}([\s\S]*?)\\end\{cases\}\\right\.?",
        lambda m: f"\\begin{{cases}}{m.group(1)}\\end{{cases}}",
        text,
    )

    def _array_to_cases(match: re.Match) -> str:
        body = str(match.group(1) or "").strip()
        return f"\\begin{{cases}}{body}\\end{{cases}}" if re.search(r"\\\\|\n", body) else body

    text = re.sub(r"\\begin\{array\}\{[^}]*\}([\s\S]*?)\\end\{array\}", _array_to_cases, text)
    text = text.replace(r"\left.", "").replace(r"\right.", "")
    text = text.replace(r"\left", "").replace(r"\right", "")
    text = re.sub(r"\\\{\s*([\s\S]*?\\\\[\s\S]*?)\s*\\\}", lambda m: f"\\begin{{cases}}{m.group(1)}\\end{{cases}}", text)
    text = re.sub(r"\\\{\s*([\s\S]*?\\\\[\s\S]*?)\s*\.{1,2}", lambda m: f"\\begin{{cases}}{m.group(1)}\\end{{cases}}", text)

    # 常见符号归一化
    replacements = {
        r"/\!//": "∥",
        r"\parallel": "∥",
        r"\perp": "⊥",
        r"\bot": "⊥",
        r"\angle": "∠",
        r"\triangle": "△",
        r"\because": "∵",
        r"\therefore": "∴",
        r"\leqslant": "≤",
        r"\leq": "≤",
        r"\geqslant": "≥",
        r"\geq": "≥",
        r"\neq": "≠",
        r"\times": "×",
        r"\div": "÷",
        r"\cdot": "·",
        r"\pm": "±",
        r"\mp": "∓",
        r"\circ": "°",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)

    text = re.sub(r"\\quad|\\qquad", " ", text)
    text = re.sub(r"\\,|\\;|\\:", " ", text)
    text = text.replace(r"\!", "")
    text = re.sub(r"\\rm\b|\\textstyle\b|\\displaystyle\b", "", text)
    text = re.sub(r"\\text\s*\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\mathrm\s*\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\operatorname\s*\{([^{}]*)\}", r"\1", text)
    text = text.replace(r"\(", "").replace(r"\)", "")
    text = text.replace(r"\[", "").replace(r"\]", "")

    # 重点修复截图里这种问题：50^^{\circ} / 30{^\circ} / ^°
    text = text.replace("^^{", "^{")
    text = text.replace("^^°", "^°")
    text = text.replace("^^{°}", "^{°}")
    text = text.replace("^^{\\circ}", "^{\\circ}")
    text = re.sub(r"\{\s*\^°\s*\}", "°", text)
    text = re.sub(r"\^°", "°", text)
    text = re.sub(r"(\d+)\s*\{\s*\\circ\s*\}", r"\1°", text)
    text = re.sub(r"(\d+)\s*\^\s*\{\s*\\circ\s*\}", r"\1°", text)
    text = re.sub(r"(\d+)\s*\\circ", r"\1°", text)

    text = re.sub(r"_+", lambda m: "____" if len(m.group(0)) >= 3 else m.group(0), text)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()



def split_top_level(s: str, delimiter: str) -> List[str]:
    parts: List[str] = []
    depth = 0
    current: List[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        if depth == 0 and s.startswith(delimiter, i):
            parts.append("".join(current))
            current = []
            i += len(delimiter)
            continue
        current.append(ch)
        i += 1
    parts.append("".join(current))
    return parts



def extract_brace_group(s: str, start_index: int) -> Optional[Tuple[str, int]]:
    if start_index >= len(s) or s[start_index] != "{":
        return None
    depth = 0
    for end in range(start_index, len(s)):
        if s[end] == "{":
            depth += 1
        elif s[end] == "}":
            depth -= 1
            if depth == 0:
                return s[start_index + 1:end], end
    return None



def read_simple_token(s: str, start_index: int) -> Tuple[str, str, int]:
    if start_index >= len(s):
        return "", "", start_index - 1
    if s[start_index] == "{":
        group = extract_brace_group(s, start_index)
        if group:
            content, end_index = group
            return content, render_inline_math_like(content), end_index
    end = start_index
    if TOKEN_CHAR_RE.match(s[start_index]):
        while end + 1 < len(s) and TOKEN_CONT_RE.match(s[end + 1]):
            end += 1
    raw = s[start_index:end + 1]
    return raw, escape_html(raw), end



def decorate_with_combining_dot(raw: str) -> str:
    safe = str(raw or "")
    if not safe:
        return ""
    chars = list(safe)
    last = chars.pop()
    return escape_html("".join(chars) + last + "\u0307")



def render_cases_block(body: str) -> str:
    lines = split_top_level(body, r"\\")
    items = "".join(
        f'<div class="formula-line">{render_inline_math_like(line.strip())}</div>'
        for line in lines if line.strip()
    )
    return f'<span class="cases"><span class="cases-brace">{{</span><span class="cases-lines">{items}</span></span>'



def render_overset(target: str, top: str) -> str:
    clean_top = re.sub(r"[{}\\]", "", normalize_text(top)).strip()
    if clean_top in {"bullet", "•", "·"}:
        token = normalize_text(target).strip()
        return f'<span class="overset-dot">{decorate_with_combining_dot(token)}</span>'
    return (
        '<span class="overset">'
        f'<span class="overset-top">{render_inline_math_like(top)}</span>'
        f'<span class="overset-base">{render_inline_math_like(target)}</span>'
        '</span>'
    )



def render_sqrt_at(s: str, i: int, cmd: str = r"\sqrt") -> Tuple[str, int]:
    start = i + len(cmd)
    group = extract_brace_group(s, start)
    if group:
        content, end_index = group
        return (
            '<span class="sqrt"><span class="sqrt-sign">√</span>'
            f'<span class="sqrt-body">{render_inline_math_like(content)}</span></span>',
            end_index,
        )
    end = start
    if end < len(s) and s[end] in "+-":
        end += 1
    while end < len(s) and re.match(r"[A-Za-z0-9.°△∠⊥∥]", s[end]):
        end += 1
    if end > start:
        raw = s[start:end]
        return (
            '<span class="sqrt"><span class="sqrt-sign">√</span>'
            f'<span class="sqrt-body">{escape_html(raw)}</span></span>',
            end - 1,
        )
    raw, token_html, end_index = read_simple_token(s, start)
    _ = raw
    return (
        '<span class="sqrt"><span class="sqrt-sign">√</span>'
        f'<span class="sqrt-body">{token_html}</span></span>',
        end_index,
    )



def render_inline_math_like(raw: Any) -> str:
    s = normalize_text(raw)
    if not s:
        return '<span class="empty-lite">—</span>'

    if (s.startswith(r"\{") or s.startswith("{")) and (r"\\" in s or "\n" in s):
        body = re.sub(r"^\\\\\{|^\{", "", s)
        body = re.sub(r"\\\\\}$|\}$", "", body).strip()
        if body:
            return render_cases_block(body)

    out: List[str] = []
    i = 0
    while i < len(s):
        if s.startswith(r"\begin{cases}", i):
            begin_len = len(r"\begin{cases}")
            end_token = r"\end{cases}"
            end_pos = s.find(end_token, i + begin_len)
            if end_pos != -1:
                body = s[i + begin_len:end_pos]
                out.append(render_cases_block(body))
                i = end_pos + len(end_token)
                continue

        if s.startswith(r"\dfrac", i) or s.startswith(r"\frac", i):
            cmd_len = 6 if s.startswith(r"\dfrac", i) else 5
            g1 = extract_brace_group(s, i + cmd_len)
            g2 = extract_brace_group(s, g1[1] + 1) if g1 else None
            if g1 and g2:
                out.append(
                    '<span class="frac">'
                    f'<span>{render_inline_math_like(g1[0])}</span>'
                    f'<span>{render_inline_math_like(g2[0])}</span>'
                    '</span>'
                )
                i = g2[1] + 1
                continue

        if s.startswith(r"\sqrt", i):
            html_part, end_index = render_sqrt_at(s, i, r"\sqrt")
            out.append(html_part)
            i = end_index + 1
            continue
        if s.startswith("sqrt", i):
            html_part, end_index = render_sqrt_at(s, i, "sqrt")
            out.append(html_part)
            i = end_index + 1
            continue

        if s.startswith(r"\boldsymbol", i) or s.startswith(r"\mathbf", i) or s.startswith(r"\bm", i):
            cmd = r"\boldsymbol" if s.startswith(r"\boldsymbol", i) else (r"\mathbf" if s.startswith(r"\mathbf", i) else r"\bm")
            group = extract_brace_group(s, i + len(cmd))
            if group:
                out.append(f'<span class="math-bold">{render_inline_math_like(group[0])}</span>')
                i = group[1] + 1
                continue

        if s.startswith(r"\overset", i):
            top = extract_brace_group(s, i + 8)
            base = extract_brace_group(s, top[1] + 1) if top else None
            if top and base:
                out.append(render_overset(base[0], top[0]))
                i = base[1] + 1
                continue

        if s.startswith(r"\oversetbullet", i) or s.startswith("oversetbullet", i):
            cmd_len = 14 if s.startswith(r"\oversetbullet", i) else 13
            raw_token, _, end_index = read_simple_token(s, i + cmd_len)
            out.append(f'<span class="overset-dot">{decorate_with_combining_dot(raw_token)}</span>')
            i = end_index + 1
            continue

        if s.startswith(r"\underline", i) or s.startswith(r"\overline", i):
            cmd_len = 10 if s.startswith(r"\underline", i) else 9
            group = extract_brace_group(s, i + cmd_len)
            if group:
                out.append(render_inline_math_like(group[0]))
                i = group[1] + 1
                continue

        if s[i] == "^":
            _, token_html, end_index = read_simple_token(s, i + 1)
            out.append(f"<sup>{token_html}</sup>")
            i = end_index + 1
            continue

        if s[i] == "_":
            _, token_html, end_index = read_simple_token(s, i + 1)
            out.append(f"<sub>{token_html}</sub>")
            i = end_index + 1
            continue

        if s.startswith(r"\\", i):
            out.append("<br />")
            i += 2
            continue

        if s[i] in "{}":
            i += 1
            continue

        if s.startswith("____", i):
            j = i
            while j < len(s) and s[j] == "_":
                j += 1
            out.append('<span class="placeholder-line"></span>')
            i = j
            continue

        if s[i] == "\n":
            out.append('<span class="sep-line"></span>')
            i += 1
            continue

        if s[i] == "\\":
            match = re.match(r"^[A-Za-z]+", s[i + 1:])
            if match:
                cmd = match.group(0)
                if cmd in KNOWN_CMD_MAP:
                    out.append(KNOWN_CMD_MAP[cmd])
                    i += len(cmd) + 1
                    continue
                if cmd in {"left", "right"}:
                    i += len(cmd) + 1
                    continue
                i += len(cmd) + 1
                continue
            i += 1
            continue

        out.append(escape_html(s[i]))
        i += 1

    html_out = "".join(out)
    html_out = re.sub(r"\s*<span class=\"sep-line\"></span>\s*", "<br />", html_out)
    html_out = re.sub(r"(<br />){3,}", "<br /><br />", html_out)
    return html_out



def render_rich_text(text: Any, compact: bool = False):
    raw = str(text or "")
    if not raw.strip():
        st.markdown('<div class="empty-lite">暂无内容</div>', unsafe_allow_html=True)
        return
    html_content = render_inline_math_like(raw)
    css_class = "math-text compact" if compact else "math-text"
    st.markdown(f'<div class="{css_class}">{html_content}</div>', unsafe_allow_html=True)


# =========================
# 图片展示
# =========================
def resolve_media_path(raw_path: str) -> Optional[Path]:
    if not raw_path:
        return None
    p = Path(raw_path)
    candidates = [
        BASE_DIR / p,
        BASE_DIR / "images" / p.name,
        BASE_DIR / "image" / p.name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None



def render_images(image_list: List[str]):
    if not image_list:
        return
    for item in image_list:
        resolved = resolve_media_path(item)
        if resolved and resolved.exists():
            st.image(str(resolved))
        else:
            st.caption(f"图片文件未找到：{item}")


# =========================
# 会话状态管理
# =========================
def get_saved_records_key(teacher_key: str) -> str:
    return f"saved_records::{teacher_key}"



def get_drafts_key(teacher_key: str) -> str:
    return f"drafts::{teacher_key}"



def get_index_key(teacher_key: str) -> str:
    return f"current_index::{teacher_key}"



def get_meta_key(teacher_key: str) -> str:
    return f"meta::{teacher_key}"



def get_current_saved_records() -> List[Dict[str, Any]]:
    return st.session_state[get_saved_records_key(st.session_state["teacher_key"])]



def set_current_saved_records(records: List[Dict[str, Any]]):
    st.session_state[get_saved_records_key(st.session_state["teacher_key"])] = records



def get_current_drafts() -> Dict[str, Any]:
    return st.session_state[get_drafts_key(st.session_state["teacher_key"])]



def set_current_drafts(drafts: Dict[str, Any]):
    st.session_state[get_drafts_key(st.session_state["teacher_key"])] = drafts



def get_current_index() -> int:
    return st.session_state[get_index_key(st.session_state["teacher_key"])]



def set_current_index(index: int):
    records = get_current_saved_records()
    total = len(records)
    safe_index = 0 if total == 0 else max(0, min(index, total - 1))
    st.session_state[get_index_key(st.session_state["teacher_key"])] = safe_index
    st.session_state["needs_state_sync"] = True



def get_current_meta() -> Dict[str, str]:
    return st.session_state[get_meta_key(st.session_state["teacher_key"])]



def set_current_meta(meta: Dict[str, str]):
    st.session_state[get_meta_key(st.session_state["teacher_key"])] = meta



def init_session():
    teacher_key = get_query_teacher()
    prev_teacher = st.session_state.get("_active_teacher")
    if prev_teacher != teacher_key:
        st.session_state["needs_state_sync"] = True

    saved_key = get_saved_records_key(teacher_key)
    drafts_key = get_drafts_key(teacher_key)
    index_key = get_index_key(teacher_key)
    meta_key = get_meta_key(teacher_key)

    if saved_key not in st.session_state:
        st.session_state[saved_key] = load_saved_records_for_teacher(teacher_key)
    if drafts_key not in st.session_state:
        st.session_state[drafts_key] = load_drafts_for_teacher(teacher_key)
    if index_key not in st.session_state:
        st.session_state[index_key] = 0
    if meta_key not in st.session_state:
        st.session_state[meta_key] = {
            "last_draft_saved_at": "",
            "last_commit_saved_at": "",
        }

    st.session_state["teacher_key"] = teacher_key
    st.session_state["_active_teacher"] = teacher_key
    st.session_state.setdefault("needs_state_sync", True)
    st.session_state.setdefault("suppress_draft_callbacks", False)


# =========================
# 草稿 / 正式保存
# =========================
def get_current_record_and_uid() -> Tuple[int, Dict[str, Any], str]:
    idx = get_current_index()
    records = get_current_saved_records()
    record = records[idx]
    uid = get_record_uid(record, idx + 1)
    return idx, record, uid



def save_drafts_to_disk():
    teacher_key = st.session_state["teacher_key"]
    write_json_atomic(get_drafts_path(teacher_key), get_current_drafts())



def save_records_to_disk():
    teacher_key = st.session_state["teacher_key"]
    write_json_atomic(get_saved_records_path(teacher_key), get_current_saved_records())



def load_annotation_into_widgets(annotation: Dict[str, Any]):
    st.session_state["suppress_draft_callbacks"] = True

    bloom = annotation.get("human_bloom_level", "") or UNSELECTED
    primary = annotation.get("human_core_literacy_primary", "") or UNSELECTED
    candidates = annotation.get("human_core_literacy_candidates", []) or []

    st.session_state["edit_bloom"] = normalize_bloom(bloom)
    st.session_state["edit_primary"] = normalize_primary(primary)
    st.session_state["edit_candidates"] = ensure_candidates_include_primary(
        primary if primary in CORE_LITERACIES else "",
        candidates,
    )
    st.session_state["edit_comment_bloom"] = str(annotation.get("human_comment_bloom", ""))
    st.session_state["edit_comment_core"] = str(annotation.get("human_comment_core", ""))

    st.session_state["suppress_draft_callbacks"] = False



def sync_widget_state(record: Dict[str, Any], uid: str):
    if not st.session_state.get("needs_state_sync", True):
        return
    drafts = get_current_drafts()
    source = drafts.get(uid) or extract_saved_annotation(record)
    load_annotation_into_widgets(source)
    st.session_state["needs_state_sync"] = False



def persist_current_draft_from_widgets():
    if st.session_state.get("suppress_draft_callbacks", False):
        return
    if "teacher_key" not in st.session_state or "edit_bloom" not in st.session_state:
        return

    _, record, uid = get_current_record_and_uid()
    annotation = build_annotation_from_widgets()
    drafts = deepcopy(get_current_drafts())
    meta = deepcopy(get_current_meta())

    if draft_equals_saved(annotation, record):
        drafts.pop(uid, None)
    else:
        drafts[uid] = {**annotation, "draft_updated_at": current_time_str()}

    set_current_drafts(drafts)
    save_drafts_to_disk()
    meta["last_draft_saved_at"] = current_time_str()
    set_current_meta(meta)



def on_primary_change():
    primary = st.session_state.get("edit_primary", UNSELECTED)
    candidates = st.session_state.get("edit_candidates", [])
    real_primary = primary if primary in CORE_LITERACIES else ""
    st.session_state["suppress_draft_callbacks"] = True
    st.session_state["edit_candidates"] = ensure_candidates_include_primary(real_primary, candidates)
    st.session_state["suppress_draft_callbacks"] = False
    persist_current_draft_from_widgets()



def on_candidates_change():
    primary = st.session_state.get("edit_primary", UNSELECTED)
    candidates = st.session_state.get("edit_candidates", [])
    real_primary = primary if primary in CORE_LITERACIES else ""
    st.session_state["suppress_draft_callbacks"] = True
    st.session_state["edit_candidates"] = ensure_candidates_include_primary(real_primary, candidates)
    st.session_state["suppress_draft_callbacks"] = False
    persist_current_draft_from_widgets()



def save_current_record(show_toast: bool = False):
    idx, record, uid = get_current_record_and_uid()
    records = deepcopy(get_current_saved_records())
    drafts = deepcopy(get_current_drafts())
    meta = deepcopy(get_current_meta())

    annotation = build_annotation_from_widgets()
    updated = deepcopy(record)
    updated.update(annotation)
    updated["human_annotator"] = st.session_state["teacher_key"]
    updated["human_updated_at"] = current_time_str()
    updated["human_status"] = "已标注" if current_is_done(updated) else "未完成"

    records[idx] = updated
    set_current_saved_records(records)
    save_records_to_disk()

    drafts.pop(uid, None)
    set_current_drafts(drafts)
    save_drafts_to_disk()

    meta["last_commit_saved_at"] = current_time_str()
    set_current_meta(meta)

    if show_toast:
        st.toast("已保存", icon="✅")



def move(delta: int):
    persist_current_draft_from_widgets()
    set_current_index(get_current_index() + delta)



def jump_to(index: int):
    persist_current_draft_from_widgets()
    set_current_index(index)



def get_record_title(i: int, record: Dict[str, Any]) -> str:
    uid = get_record_uid(record, i + 1)
    drafts = get_current_drafts()
    status = "📝" if uid in drafts else ("✅" if current_is_done(record) else "⬜")
    return f"{status} 第{i + 1}题 · {uid}"



def make_export_name(teacher_key: str) -> str:
    return f"{teacher_key}_annotations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"


# =========================
# 页面
# =========================
init_session()

teacher_key = st.session_state["teacher_key"]
teacher_label = TASK_MAP[teacher_key]["label"]
records = get_current_saved_records()
drafts = get_current_drafts()
meta = get_current_meta()
total = len(records)

st.title("数字题人工标注工具")

with st.sidebar:
    st.subheader("当前任务")
    st.write(f"**任务：** {teacher_label}")
    st.write(f"**参数：** `{teacher_key}`")

    done_count = sum(1 for item in records if current_is_done(item))
    st.metric("总题数", total)
    st.metric("已保存", done_count)
    st.metric("未保存", total - done_count)
    st.metric("暂存草稿", len(drafts))
    st.progress(done_count / total if total else 0.0)
    st.caption("✅ 已保存　📝 有暂存未保存　⬜ 未开始")

    if meta.get("last_commit_saved_at"):
        st.caption(f"最近正式保存：{meta['last_commit_saved_at']}")
    if meta.get("last_draft_saved_at"):
        st.caption(f"最近草稿暂存：{meta['last_draft_saved_at']}")

    st.divider()
    only_unfinished = st.checkbox("只看未保存题", value=False)
    visible_indices = [
        i for i, record in enumerate(records)
        if (not only_unfinished) or (not current_is_done(record))
    ]

    if visible_indices:
        title_map = {get_record_title(i, records[i]): i for i in visible_indices}
        titles = list(title_map.keys())
        current_index = get_current_index()
        default_pos = visible_indices.index(current_index) if current_index in visible_indices else 0

        selected_title = st.selectbox("题目列表", titles, index=default_pos)
        selected_index = title_map[selected_title]
        if selected_index != current_index:
            jump_to(selected_index)
            st.rerun()

        if st.button("跳到下一道未保存题", use_container_width=True):
            unfinished = [i for i, item in enumerate(records) if not current_is_done(item)]
            if unfinished:
                current = get_current_index()
                target = next((i for i in unfinished if i > current), unfinished[0])
                jump_to(target)
                st.rerun()
    else:
        st.success("当前任务已全部保存完成。")

    st.divider()
    st.download_button(
        "下载当前标注结果 JSON",
        data=dump_records_bytes(records),
        file_name=make_export_name(teacher_key),
        mime="application/json",
        use_container_width=True,
    )

if total == 0:
    st.warning("当前没有可标注题目。")
    st.stop()

idx = get_current_index()
record = records[idx]
uid = get_record_uid(record, idx + 1)
sync_widget_state(record, uid)

current_widget_annotation = build_annotation_from_widgets()
has_unsaved_draft = not draft_equals_saved(current_widget_annotation, record)

nav1, nav2, nav3, nav4 = st.columns([1, 1, 1, 1])
with nav1:
    if st.button("⬅ 上一题", disabled=(idx == 0), use_container_width=True):
        move(-1)
        st.rerun()
with nav2:
    if st.button("下一题 ➡", disabled=(idx == total - 1), use_container_width=True):
        move(1)
        st.rerun()
with nav3:
    if st.button("保存并下一题", use_container_width=True, type="primary"):
        save_current_record(show_toast=True)
        if idx < total - 1:
            set_current_index(idx + 1)
        st.rerun()
with nav4:
    st.info(f"{teacher_label}：第 {idx + 1} / {total} 题")

left, right = st.columns([1.7, 1], gap="large")

with left:
    st.markdown("## 题目区")
    with st.container(height=1040, border=True):
        st.markdown(f"**题目ID：** `{uid}`")
        st.markdown(f"**题型：** {record.get('type', '') or '—'}")
        if record.get("difficulty"):
            st.markdown(f"**难度：** {record.get('difficulty', '')}")
        if record.get("grades"):
            grades = record.get("grades", [])
            if isinstance(grades, list):
                st.markdown(f"**年级：** {'、'.join(map(str, grades))}")

        st.markdown("### 题干")
        render_rich_text(get_display_stem(record))

        if record.get("stem_images"):
            st.markdown("### 题干图片")
            render_images(record.get("stem_images", []))

        if record.get("options"):
            st.markdown("### 选项")
            for option in record.get("options", []):
                option_label = escape_html(option.get("index", ""))
                option_html = render_inline_math_like(option.get("text", ""))
                st.markdown(
                    f'<div class="option-card"><div class="option-label">{option_label}</div>'
                    f'<div class="math-text compact">{option_html}</div></div>',
                    unsafe_allow_html=True,
                )
                if option.get("images"):
                    render_images(option.get("images", []))

        st.markdown("### 参考答案")
        render_rich_text(record.get("answer", ""))

        st.markdown("### 解析")
        render_rich_text(get_display_analysis(record))

        if record.get("analysis_images"):
            st.markdown("### 解析图片")
            render_images(record.get("analysis_images", []))

with right:
    saved_status = get_saved_status_text(record)
    draft_status = "有未保存修改" if has_unsaved_draft else "当前内容已与保存记录同步"
    st.markdown(
        f"<div class='status-line'>保存状态：{saved_status}｜当前状态：{draft_status}</div>",
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        model_bloom = record.get("bloom_level", "") or "无"
        model_primary = record.get("core_literacy_primary", "") or "无"
        model_candidates = record.get("core_literacy_candidates", []) or []
        model_candidates_text = "、".join(map(str, model_candidates)) if model_candidates else "无"

        st.markdown("### 模型建议")
        st.markdown(
            "<div class='model-card'>"
            f"<div class='model-row'><strong>Bloom：</strong> {escape_html(model_bloom)}</div>"
            f"<div class='model-row'><strong>核心素养主标签：</strong> {escape_html(model_primary)}</div>"
            f"<div class='model-row'><strong>核心素养候选：</strong> {escape_html(model_candidates_text)}</div>"
            "</div>",
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
            on_change=persist_current_draft_from_widgets,
        )
        st.text_area(
            "Bloom 备注",
            key="edit_comment_bloom",
            height=90,
            on_change=persist_current_draft_from_widgets,
        )

    st.write("")

    with st.container(border=True):
        st.markdown("### 核心素养标注")
        st.selectbox(
            "核心素养主标签",
            options=PRIMARY_OPTIONS,
            key="edit_primary",
            on_change=on_primary_change,
        )
        st.multiselect(
            "核心素养候选（最多 3 个）",
            options=CORE_LITERACIES,
            key="edit_candidates",
            max_selections=3,
            on_change=on_candidates_change,
        )
        st.text_area(
            "核心素养备注",
            key="edit_comment_core",
            height=90,
            on_change=persist_current_draft_from_widgets,
        )

    st.write("")
    btn1, btn2 = st.columns(2)
    with btn1:
        if st.button("保存当前题", use_container_width=True):
            save_current_record(show_toast=True)
            st.rerun()
    with btn2:
        if st.button("跳过本题", use_container_width=True):
            if idx < total - 1:
                move(1)
            st.rerun()
