
import json
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
BLOOM_LEVELS = ["记忆", "理解", "应用", "分析", "评价", "创造"]
CORE_LITERACIES = [
    "抽象能力", "运算能力", "几何直观", "空间观念", "推理能力",
    "数据观念", "模型观念", "应用意识", "创新意识",
]

# 按需改成你的真实文件路径。老师只需要访问你分发给他们的 ?task=teacher1 / teacher2 / teacher3 链接。
TASKS = {
    "teacher1": {"label": "教师 1", "data_file": "teacher_1.json"},
    "teacher2": {"label": "教师 2", "data_file": "teacher_2.json"},
    "teacher3": {"label": "教师 3", "data_file": "teacher_3.json"},
}

BASE_DIR = Path(__file__).parent
ASSET_DIRS = [BASE_DIR, BASE_DIR / "data", BASE_DIR / "images"]
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# 样式
# =========================
st.markdown("""
<style>
.block-container {
    padding-top: 1rem;
    padding-bottom: 1.6rem;
}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stCheckbox label {
    font-size: 0.95rem;
}
.question-wrap {
    line-height: 1.8;
    font-size: 1.02rem;
}
.question-wrap p {
    margin: 0.2rem 0 0.6rem 0;
}
.model-card {
    background: #f7f8fb;
    border: 1px solid #e7eaf3;
    border-radius: 12px;
    padding: 0.75rem 0.9rem;
    margin-bottom: 0.75rem;
}
.model-row {
    margin: 0.2rem 0;
    color: #333;
}
.blank-inline {
    display: inline-block;
    min-width: 6em;
    border-bottom: 1.8px solid #666;
    transform: translateY(-0.12em);
}
.small-muted {
    color: #666;
    font-size: 0.92rem;
}
.feedback-ok {
    color: #157347;
    font-weight: 600;
}
.feedback-warn {
    color: #9a6700;
    font-weight: 600;
}
.feedback-error {
    color: #b42318;
    font-weight: 600;
}
div[data-testid="stImage"] img {
    max-height: 360px !important;
    width: auto !important;
    object-fit: contain;
    border-radius: 4px;
}
</style>
""", unsafe_allow_html=True)


# =========================
# I/O
# =========================
def load_json_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        st.error(f"未找到数据文件：{path}")
        st.stop()

    try:
        text = path.read_text(encoding="utf-8").strip()
    except Exception as e:
        st.error(f"读取文件失败：{path}\n{e}")
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


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json_or_default(path: Path, default: Any) -> Any:
    if not path.exists():
        return deepcopy(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return deepcopy(default)


def get_task_key() -> str:
    task = st.query_params.get("task", "teacher1")
    if isinstance(task, list):
        task = task[0] if task else "teacher1"
    task = str(task).strip()
    return task if task in TASKS else "teacher1"


def task_output_paths(task_key: str) -> Dict[str, Path]:
    return {
        "saved": OUTPUT_DIR / f"{task_key}_saved.json",
        "drafts": OUTPUT_DIR / f"{task_key}_drafts.json",
    }


# =========================
# 数据字段
# =========================
def record_id(record: Dict[str, Any], idx: int) -> str:
    return str(record.get("id") or record.get("sample_id") or f"item_{idx+1}")


def is_saved_done(record: Dict[str, Any]) -> bool:
    return bool(record.get("human_bloom_level")) and bool(record.get("human_core_literacy_primary"))


def build_saved_index(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result = {}
    for idx, item in enumerate(records):
        rid = record_id(item, idx)
        if any(k.startswith("human_") for k in item.keys()):
            result[rid] = {
                "human_bloom_level": item.get("human_bloom_level", ""),
                "human_core_literacy_primary": item.get("human_core_literacy_primary", ""),
                "human_core_literacy_candidates": item.get("human_core_literacy_candidates", []),
                "human_comment_bloom": item.get("human_comment_bloom", ""),
                "human_comment_core": item.get("human_comment_core", ""),
                "human_annotator": item.get("human_annotator", ""),
                "human_updated_at": item.get("human_updated_at", ""),
                "human_status": item.get("human_status", ""),
            }
    return result


def export_minimal_annotations(records: List[Dict[str, Any]]) -> bytes:
    rows = []
    for idx, item in enumerate(records):
        if not any(k.startswith("human_") for k in item.keys()):
            continue
        rows.append({
            "id": record_id(item, idx),
            "human_bloom_level": item.get("human_bloom_level", ""),
            "human_core_literacy_primary": item.get("human_core_literacy_primary", ""),
            "human_core_literacy_candidates": item.get("human_core_literacy_candidates", []),
            "human_comment_bloom": item.get("human_comment_bloom", ""),
            "human_comment_core": item.get("human_comment_core", ""),
            "human_annotator": item.get("human_annotator", ""),
            "human_updated_at": item.get("human_updated_at", ""),
            "human_status": item.get("human_status", ""),
        })
    return json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")


# =========================
# 轻量文本处理：normalized_* 优先，标准 LaTeX 优先
# =========================
INLINE_MATH_RE = re.compile(r"(\$\$.*?\$\$|\$.*?\$)", re.S)
DEGREE_FIX_RE = re.compile(r"\^\^\{\\circ\}|\^\^\{°\}")
NUMBER_DEG_FIX_RE = re.compile(r"(\d+)\{\^\\circ\}")
BAD_FRAC_RE = re.compile(r"\\([dtc]?frac)\s*")


def normalize_latex_text(text: Any) -> str:
    s = "" if text is None else str(text)
    s = s.replace("\u00a0", " ").replace("\r\n", "\n").replace("\r", "\n")
    s = DEGREE_FIX_RE.sub(r"^{\\circ}", s)
    s = NUMBER_DEG_FIX_RE.sub(r"\1^{\\circ}", s)
    s = BAD_FRAC_RE.sub(r"\\frac", s)
    return s.strip()


def process_plain_segment(segment: str) -> str:
    s = segment
    # 填空横线：优先展示成可见下划线，不动 LaTeX 数学命令
    s = re.sub(r"\\{3,}", r"\\_\\_\\_\\_", s)
    s = re.sub(r"_{4,}", r"\\_\\_\\_\\_", s)
    return s


def prepare_mixed_markdown(text: Any) -> str:
    raw = normalize_latex_text(text)
    if not raw:
        return "—"
    parts = INLINE_MATH_RE.split(raw)
    processed = []
    for part in parts:
        if not part:
            continue
        if part.startswith("$") and part.endswith("$"):
            processed.append(part)
        else:
            processed.append(process_plain_segment(part))
    return "".join(processed)


def render_text_block(title: str, text: Any) -> None:
    st.markdown(f"### {title}")
    md = prepare_mixed_markdown(text)
    st.markdown(f"<div class='question-wrap'>{md}</div>", unsafe_allow_html=True)


def render_images(paths: List[str]) -> None:
    if not isinstance(paths, list) or not paths:
        return
    for path_str in paths:
        resolved = resolve_media_path(path_str)
        if resolved and resolved.exists():
            st.image(str(resolved))
        else:
            st.caption(f"图片文件未找到：{path_str}")


def resolve_media_path(raw_path: str) -> Optional[Path]:
    if not raw_path:
        return None
    p = Path(str(raw_path))
    candidates = [
        BASE_DIR / p,
        BASE_DIR / "images" / p.name,
        BASE_DIR / "image" / p.name,
    ]
    for c in candidates:
        if c.exists():
            return c
    return BASE_DIR / p


# =========================
# 标注状态
# =========================
def current_time_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_candidates(primary: str, candidates: List[str]) -> List[str]:
    cleaned = []
    for x in candidates or []:
        if x in CORE_LITERACIES and x not in cleaned:
            cleaned.append(x)
    if primary in CORE_LITERACIES:
        if primary in cleaned:
            cleaned.remove(primary)
        cleaned = [primary] + cleaned
    return cleaned[:3]


def annotation_from_sources(record: Dict[str, Any], rid: str, drafts_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    if rid in drafts_map:
        src = drafts_map[rid]
        bloom = src.get("human_bloom_level") or record.get("human_bloom_level") or record.get("bloom_level") or ""
        primary = src.get("human_core_literacy_primary") or record.get("human_core_literacy_primary") or record.get("core_literacy_primary") or ""
        candidates = src.get("human_core_literacy_candidates") or record.get("human_core_literacy_candidates") or record.get("core_literacy_candidates") or []
        return {
            "human_bloom_level": bloom,
            "human_core_literacy_primary": primary,
            "human_core_literacy_candidates": ensure_candidates(primary, candidates),
            "human_comment_bloom": src.get("human_comment_bloom", record.get("human_comment_bloom", "")),
            "human_comment_core": src.get("human_comment_core", record.get("human_comment_core", "")),
        }

    bloom = record.get("human_bloom_level") or record.get("bloom_level") or ""
    primary = record.get("human_core_literacy_primary") or record.get("core_literacy_primary") or ""
    candidates = record.get("human_core_literacy_candidates") or record.get("core_literacy_candidates") or []
    return {
        "human_bloom_level": bloom,
        "human_core_literacy_primary": primary,
        "human_core_literacy_candidates": ensure_candidates(primary, candidates),
        "human_comment_bloom": record.get("human_comment_bloom", ""),
        "human_comment_core": record.get("human_comment_core", ""),
    }


def draft_for_current() -> Dict[str, Any]:
    return {
        "human_bloom_level": st.session_state.get("edit_bloom", ""),
        "human_core_literacy_primary": st.session_state.get("edit_primary", ""),
        "human_core_literacy_candidates": ensure_candidates(
            st.session_state.get("edit_primary", ""),
            st.session_state.get("edit_candidates", []),
        ),
        "human_comment_bloom": st.session_state.get("edit_comment_bloom", "").strip(),
        "human_comment_core": st.session_state.get("edit_comment_core", "").strip(),
    }


def draft_equals(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return (
        a.get("human_bloom_level", "") == b.get("human_bloom_level", "") and
        a.get("human_core_literacy_primary", "") == b.get("human_core_literacy_primary", "") and
        ensure_candidates(a.get("human_core_literacy_primary", ""), a.get("human_core_literacy_candidates", []))
        == ensure_candidates(b.get("human_core_literacy_primary", ""), b.get("human_core_literacy_candidates", [])) and
        (a.get("human_comment_bloom", "") or "").strip() == (b.get("human_comment_bloom", "") or "").strip() and
        (a.get("human_comment_core", "") or "").strip() == (b.get("human_comment_core", "") or "").strip()
    )


def save_hidden_draft(records: List[Dict[str, Any]], idx: int, drafts_map: Dict[str, Dict[str, Any]], draft_path: Path) -> None:
    rid = record_id(records[idx], idx)
    current = draft_for_current()
    saved = {
        "human_bloom_level": records[idx].get("human_bloom_level", ""),
        "human_core_literacy_primary": records[idx].get("human_core_literacy_primary", ""),
        "human_core_literacy_candidates": records[idx].get("human_core_literacy_candidates", []),
        "human_comment_bloom": records[idx].get("human_comment_bloom", ""),
        "human_comment_core": records[idx].get("human_comment_core", ""),
    }
    if draft_equals(current, saved):
        if rid in drafts_map:
            drafts_map.pop(rid, None)
            write_json(draft_path, drafts_map)
        return

    if not any([current["human_bloom_level"], current["human_core_literacy_primary"], current["human_comment_bloom"], current["human_comment_core"], current["human_core_literacy_candidates"]]):
        if rid in drafts_map:
            drafts_map.pop(rid, None)
            write_json(draft_path, drafts_map)
        return

    drafts_map[rid] = current
    write_json(draft_path, drafts_map)


def validate_for_save() -> Optional[str]:
    bloom = st.session_state.get("edit_bloom", "")
    primary = st.session_state.get("edit_primary", "")
    if not bloom or bloom not in BLOOM_LEVELS:
        return "请先选择 Bloom 层级。"
    if not primary or primary not in CORE_LITERACIES:
        return "请先选择核心素养主标签。"
    return None


def save_current_record(records: List[Dict[str, Any]], idx: int, task_key: str, drafts_map: Dict[str, Dict[str, Any]], saved_path: Path, draft_path: Path) -> Tuple[bool, str]:
    error = validate_for_save()
    if error:
        return False, error

    record = deepcopy(records[idx])
    record["human_bloom_level"] = st.session_state.get("edit_bloom", "")
    record["human_core_literacy_primary"] = st.session_state.get("edit_primary", "")
    record["human_core_literacy_candidates"] = ensure_candidates(
        st.session_state.get("edit_primary", ""),
        st.session_state.get("edit_candidates", []),
    )
    record["human_comment_bloom"] = st.session_state.get("edit_comment_bloom", "").strip()
    record["human_comment_core"] = st.session_state.get("edit_comment_core", "").strip()
    record["human_annotator"] = task_key
    record["human_updated_at"] = current_time_str()
    record["human_status"] = "已标注"

    records[idx] = record
    write_json(saved_path, records)

    rid = record_id(record, idx)
    if rid in drafts_map:
        drafts_map.pop(rid, None)
        write_json(draft_path, drafts_map)

    st.session_state["feedback"] = ("ok", f"第 {idx + 1} 题已保存。")
    st.session_state["last_saved_idx"] = idx
    return True, "保存成功"


# =========================
# 会话初始化
# =========================
def init_app_state() -> None:
    task_key = get_task_key()
    if "task_key" not in st.session_state or st.session_state["task_key"] != task_key:
        st.session_state["task_key"] = task_key
        st.session_state["need_sync"] = True
        st.session_state["feedback"] = None

    st.query_params["task"] = task_key

    if "loaded" not in st.session_state or st.session_state["loaded"] != task_key:
        source_path = BASE_DIR / TASKS[task_key]["data_file"]
        paths = task_output_paths(task_key)
        base_records = load_json_records(source_path)

        saved_records = load_json_or_default(paths["saved"], base_records)
        drafts_map = load_json_or_default(paths["drafts"], {})

        st.session_state["records"] = saved_records
        st.session_state["drafts_map"] = drafts_map
        st.session_state["saved_path"] = paths["saved"]
        st.session_state["draft_path"] = paths["drafts"]
        st.session_state["current_index"] = 0
        st.session_state["loaded"] = task_key
        st.session_state["need_sync"] = True

    st.session_state.setdefault("feedback", None)
    st.session_state.setdefault("last_saved_idx", None)


def sync_widgets_from_record(records: List[Dict[str, Any]], idx: int, drafts_map: Dict[str, Dict[str, Any]]) -> None:
    if not st.session_state.get("need_sync", True):
        return
    record = records[idx]
    rid = record_id(record, idx)
    ann = annotation_from_sources(record, rid, drafts_map)

    bloom = ann["human_bloom_level"] if ann["human_bloom_level"] in BLOOM_LEVELS else (record.get("bloom_level") if record.get("bloom_level") in BLOOM_LEVELS else "")
    primary = ann["human_core_literacy_primary"] if ann["human_core_literacy_primary"] in CORE_LITERACIES else (record.get("core_literacy_primary") if record.get("core_literacy_primary") in CORE_LITERACIES else "")
    candidates = ensure_candidates(primary, ann["human_core_literacy_candidates"])

    st.session_state["edit_bloom"] = bloom
    st.session_state["edit_primary"] = primary
    st.session_state["edit_candidates"] = candidates
    st.session_state["edit_comment_bloom"] = ann["human_comment_bloom"]
    st.session_state["edit_comment_core"] = ann["human_comment_core"]
    st.session_state["need_sync"] = False


def move_to(index: int, records: List[Dict[str, Any]], drafts_map: Dict[str, Dict[str, Any]], draft_path: Path) -> None:
    current = st.session_state["current_index"]
    save_hidden_draft(records, current, drafts_map, draft_path)
    st.session_state["current_index"] = max(0, min(index, len(records) - 1))
    st.session_state["need_sync"] = True


def status_icon(record: Dict[str, Any], idx: int, drafts_map: Dict[str, Dict[str, Any]]) -> str:
    if is_saved_done(record):
        return "✅"
    rid = record_id(record, idx)
    if rid in drafts_map:
        return "📝"
    return "⬜"


def question_title(record: Dict[str, Any], idx: int, drafts_map: Dict[str, Dict[str, Any]]) -> str:
    icon = status_icon(record, idx, drafts_map)
    return f"{icon} 第{idx + 1}题 · {record_id(record, idx)}"


# =========================
# 页面
# =========================
init_app_state()

task_key = st.session_state["task_key"]
records = st.session_state["records"]
drafts_map = st.session_state["drafts_map"]
saved_path = st.session_state["saved_path"]
draft_path = st.session_state["draft_path"]
total = len(records)

if total == 0:
    st.warning("当前没有可标注题目。")
    st.stop()

idx = st.session_state["current_index"]
sync_widgets_from_record(records, idx, drafts_map)
record = records[idx]
rid = record_id(record, idx)

st.title("数字题人工标注工具")

with st.sidebar:
    done_count = sum(1 for x in records if is_saved_done(x))
    st.metric("总题数", total)
    st.metric("已保存", done_count)
    st.metric("未保存", total - done_count)
    st.progress(done_count / total if total else 0.0)

    st.divider()
    only_unsaved = st.checkbox("只看未保存题", value=False)
    visible_indices = [i for i, r in enumerate(records) if (not only_unsaved) or (not is_saved_done(r))]

    if visible_indices:
        labels = [question_title(records[i], i, drafts_map) for i in visible_indices]
        label_to_idx = dict(zip(labels, visible_indices))
        default_pos = visible_indices.index(idx) if idx in visible_indices else 0
        selected_label = st.selectbox("题目列表", labels, index=default_pos)
        target_idx = label_to_idx[selected_label]
        if target_idx != idx:
            move_to(target_idx, records, drafts_map, draft_path)
            st.rerun()

        if st.button("跳到下一道未保存题", use_container_width=True):
            unsaved = [i for i, r in enumerate(records) if not is_saved_done(r)]
            if unsaved:
                nxt = next((i for i in unsaved if i > idx), unsaved[0])
                move_to(nxt, records, drafts_map, draft_path)
                st.rerun()

    st.divider()
    st.download_button(
        "下载标注结果 JSON",
        data=export_minimal_annotations(records),
        file_name=f"{task_key}_annotations_minimal.json",
        mime="application/json",
        use_container_width=True,
    )

left, right = st.columns([1.7, 1], gap="large")

with left:
    st.markdown("## 题目区")
    with st.container(height=980, border=True):
        st.markdown(f"**题目ID：** `{rid}`")
        meta = []
        if record.get("type"):
            meta.append(f"题型：{record.get('type')}")
        if record.get("score") is not None:
            meta.append(f"分值：{record.get('score')}")
        if record.get("difficulty"):
            meta.append(f"难度：{record.get('difficulty')}")
        if record.get("grades"):
            meta.append(f"年级：{'、'.join(record.get('grades', []))}")
        if meta:
            st.markdown(" · ".join(meta))

        render_text_block("题干", record.get("normalized_stem") )
        if record.get("stem_images"):
            st.markdown("### 题干图片")
            render_images(record.get("stem_images", []))

        if record.get("options"):
            st.markdown("### 选项")
            for opt in record.get("options", []):
                label = opt.get("index", "")
                text = opt.get("text", "")
                st.markdown(f"**{label}.**")
                st.markdown(f"<div class='question-wrap'>{prepare_mixed_markdown(text)}</div>", unsafe_allow_html=True)
                if opt.get("images"):
                    render_images(opt.get("images", []))

        render_text_block("参考答案", record.get("answer", ""))
        render_text_block("解析", record.get("normalized_analysis") or record.get("analysis") or "")
        if record.get("analysis_images"):
            st.markdown("### 解析图片")
            render_images(record.get("analysis_images", []))

with right:
    st.markdown("## 标注区")
    feedback = st.session_state.get("feedback")
    if feedback:
        level, message = feedback
        cls = "feedback-ok" if level == "ok" else ("feedback-warn" if level == "warn" else "feedback-error")
        st.markdown(f"<div class='{cls}'>{message}</div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("### 模型建议")
        bloom_reason = record.get("bloom_reason", "") or "—"
        core_reason = record.get("core_literacy_reason", "") or "—"
        model_candidates = "、".join(record.get("core_literacy_candidates", [])) if record.get("core_literacy_candidates") else "—"

        st.markdown(f"""
        <div class="model-card">
          <div class="model-row"><b>Bloom：</b>{record.get("bloom_level", "—") or "—"}</div>
          <div class="model-row"><b>Bloom 理由：</b>{bloom_reason}</div>
          <div class="model-row"><b>核心素养主标签：</b>{record.get("core_literacy_primary", "—") or "—"}</div>
          <div class="model-row"><b>核心素养候选：</b>{model_candidates}</div>
          <div class="model-row"><b>核心素养理由：</b>{core_reason}</div>
        </div>
        """, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(f"### 当前题：第 {idx + 1} / {total} 题")
        st.radio(
            "Bloom 层级",
            options=BLOOM_LEVELS,
            key="edit_bloom",
            horizontal=True,
            index=BLOOM_LEVELS.index(st.session_state["edit_bloom"]) if st.session_state.get("edit_bloom") in BLOOM_LEVELS else None,
        )
        st.text_area("Bloom 备注", key="edit_comment_bloom", height=80)

        st.selectbox(
            "核心素养主标签",
            options=[""] + CORE_LITERACIES,
            key="edit_primary",
            format_func=lambda x: "请选择" if x == "" else x,
        )

        current_candidates = ensure_candidates(
            st.session_state.get("edit_primary", ""),
            st.session_state.get("edit_candidates", []),
        )
        st.session_state["edit_candidates"] = current_candidates

        st.multiselect(
            "核心素养候选（最多 3 个）",
            options=CORE_LITERACIES,
            key="edit_candidates",
            max_selections=3,
        )
        st.text_area("核心素养备注", key="edit_comment_core", height=80)

        btn1, btn2, btn3 = st.columns(3)
        with btn1:
            if st.button("上一题", use_container_width=True, disabled=(idx == 0)):
                move_to(idx - 1, records, drafts_map, draft_path)
                st.session_state["feedback"] = None
                st.rerun()
        with btn2:
            if st.button("下一题", use_container_width=True, disabled=(idx == total - 1)):
                move_to(idx + 1, records, drafts_map, draft_path)
                st.session_state["feedback"] = None
                st.rerun()
        with btn3:
            if st.button("保存并下一题", use_container_width=True, type="primary"):
                ok, msg = save_current_record(records, idx, task_key, drafts_map, saved_path, draft_path)
                st.session_state["records"] = records
                st.session_state["drafts_map"] = drafts_map
                if ok:
                    if idx < total - 1:
                        st.session_state["current_index"] = idx + 1
                        st.session_state["need_sync"] = True
                    st.rerun()
                else:
                    st.session_state["feedback"] = ("warn", msg)
                    st.rerun()

        if st.button("保存当前题", use_container_width=True):
            ok, msg = save_current_record(records, idx, task_key, drafts_map, saved_path, draft_path)
            st.session_state["records"] = records
            st.session_state["drafts_map"] = drafts_map
            if not ok:
                st.session_state["feedback"] = ("warn", msg)
            st.rerun()

# 页面底部：静默保留当前题草稿
save_hidden_draft(records, idx, drafts_map, draft_path)
st.session_state["drafts_map"] = drafts_map
