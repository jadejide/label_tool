import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

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
# 样式
# =========================
st.markdown(
    """
<style>
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
}
[data-testid="stImage"] img {
    max-height: 300px !important;
    width: auto !important;
    object-fit: contain;
    border-radius: 4px;
}
.small-muted {
    color: #666;
    font-size: 0.92rem;
}
.status-line {
    font-size: 0.92rem;
    color: #666;
    margin-top: -0.4rem;
    margin-bottom: 0.4rem;
}
</style>
""",
    unsafe_allow_html=True,
)


# =========================
# 文件与 JSON
# =========================
def read_json_file(path: Path, default: Any):
    if not path.exists():
        return deepcopy(default)
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return deepcopy(default)
        return json.loads(text)
    except Exception as e:
        st.warning(f"读取文件失败：{path.name}，已使用默认值。{e}")
        return deepcopy(default)


def write_json_atomic(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(data, ensure_ascii=False, indent=2)
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)



def load_json_records(path: Path):
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
            records = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            records = json.loads(text)
    except json.JSONDecodeError as e:
        st.error(f"JSON 解析失败：{path}\n{e}")
        st.stop()

    if not isinstance(records, list):
        st.error("数据文件必须是 JSON 数组或 JSONL。")
        st.stop()

    return records



def dump_records_bytes(records):
    return json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")



def get_saved_records_path(teacher_key: str) -> Path:
    return DATA_DIR / f"{teacher_key}_saved.json"



def get_legacy_autosave_path(teacher_key: str) -> Path:
    return DATA_DIR / f"{teacher_key}_autosave.json"



def get_drafts_path(teacher_key: str) -> Path:
    return DATA_DIR / f"{teacher_key}_drafts.json"



def load_saved_records_for_teacher(teacher_key: str):
    saved_path = get_saved_records_path(teacher_key)
    legacy_path = get_legacy_autosave_path(teacher_key)
    original_path = BASE_DIR / TASK_MAP[teacher_key]["file"]

    if saved_path.exists():
        return load_json_records(saved_path)
    if legacy_path.exists():
        return load_json_records(legacy_path)
    return load_json_records(original_path)



def load_drafts_for_teacher(teacher_key: str):
    data = read_json_file(get_drafts_path(teacher_key), default={})
    return data if isinstance(data, dict) else {}


# =========================
# 通用工具
# =========================
def current_time_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")



def get_query_teacher():
    teacher = st.query_params.get("teacher", "teacher1")
    if isinstance(teacher, list):
        teacher = teacher[0] if teacher else "teacher1"
    teacher = str(teacher).strip()
    if teacher not in TASK_MAP:
        teacher = "teacher1"
    return teacher



def get_record_uid(record: dict, idx: int) -> str:
    return str(record.get("id") or record.get("sample_id") or f"item_{idx}")



def ensure_candidates_include_primary(primary, candidates):
    clean = []
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



def normalize_annotation(annotation: dict) -> dict:
    bloom = normalize_bloom(annotation.get("human_bloom_level", UNSELECTED))
    primary = normalize_primary(annotation.get("human_core_literacy_primary", UNSELECTED))
    primary_real = primary if primary in CORE_LITERACIES else ""
    candidates = ensure_candidates_include_primary(primary_real, annotation.get("human_core_literacy_candidates", []))
    return {
        "human_bloom_level": "" if bloom == UNSELECTED else bloom,
        "human_core_literacy_primary": primary_real,
        "human_core_literacy_candidates": candidates,
        "human_comment_bloom": str(annotation.get("human_comment_bloom", "")).strip(),
        "human_comment_core": str(annotation.get("human_comment_core", "")).strip(),
    }



def extract_saved_annotation(record: dict) -> dict:
    return normalize_annotation(
        {
            "human_bloom_level": record.get("human_bloom_level", ""),
            "human_core_literacy_primary": record.get("human_core_literacy_primary", ""),
            "human_core_literacy_candidates": record.get("human_core_literacy_candidates", []),
            "human_comment_bloom": record.get("human_comment_bloom", ""),
            "human_comment_core": record.get("human_comment_core", ""),
        }
    )



def build_annotation_from_widgets() -> dict:
    return normalize_annotation(
        {
            "human_bloom_level": st.session_state.get("edit_bloom", UNSELECTED),
            "human_core_literacy_primary": st.session_state.get("edit_primary", UNSELECTED),
            "human_core_literacy_candidates": st.session_state.get("edit_candidates", []),
            "human_comment_bloom": st.session_state.get("edit_comment_bloom", ""),
            "human_comment_core": st.session_state.get("edit_comment_core", ""),
        }
    )



def current_is_done(record: dict) -> bool:
    saved = extract_saved_annotation(record)
    return bool(saved["human_bloom_level"]) and bool(saved["human_core_literacy_primary"])



def get_saved_status_text(record: dict) -> str:
    return "已保存" if current_is_done(record) else "未保存"


GREEK_CHAR_MAP = {
    "α": r"\alpha",
    "β": r"\beta",
    "γ": r"\gamma",
    "θ": r"\theta",
    "λ": r"\lambda",
    "μ": r"\mu",
    "π": r"\pi",
}


# =========================
# 数学文本渲染
# =========================
def sanitize_math_text(text: str) -> str:
    if text is None:
        return ""

    s = str(text)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"\\\((q+uad)\)", " ", s)
    s = s.replace("\\(", "$").replace("\\)", "$")
    s = s.replace("\\[", "$$").replace("\\]", "$$")
    s = s.replace("⩽", "\\leqslant")
    s = s.replace("⩾", "\\geqslant")
    s = s.replace("≤", "\\leq")
    s = s.replace("≥", "\\geq")
    s = s.replace("∠", "\\angle ")
    s = s.replace("∵", "\\because ")
    s = s.replace("∴", "\\therefore ")
    s = s.replace("×", "\\times ")
    s = s.replace("÷", "\\div ")
    s = s.replace("。。", "。")
    s = s.replace("^^{", "^{")
    s = s.replace("^^\\circ", "^\\circ")
    s = s.replace("^^{\\circ}", "^{\\circ}")
    s = s.replace("^^{\\\\circ}", "^{\\circ}")
    s = s.replace("^^\\\\circ", "^\\circ")

    for k, v in GREEK_CHAR_MAP.items():
        s = s.replace(k, v)

    s = re.sub(r"(\d+)\s*\{\s*\\circ\s*\}", r"\1^{\\circ}", s)
    s = re.sub(r"(\d+)\s*\^\s*\{\s*\\circ\s*\}", r"\1^{\\circ}", s)
    s = re.sub(r"(\d+)\s*\^\s*\\circ", r"\1^{\\circ}", s)
    s = re.sub(r"(\d+)\s*\\circ", r"\1^{\\circ}", s)
    s = re.sub(r"\\angle\s*([A-Za-z])", r"\\angle \1", s)
    s = re.sub(r"(?<![A-Za-z])([A-Za-z]{2,})\s*//\s*([A-Za-z]{2,})", r"\1 \\parallel \2", s)

    s = s.replace("\u00a0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def latex_to_readable_text(text: str) -> str:
    if not text:
        return ""

    s = text
    replacements = {
        "$$": "",
        "$": "",
        r"\alpha": "α",
        r"\beta": "β",
        r"\gamma": "γ",
        r"\theta": "θ",
        r"\lambda": "λ",
        r"\mu": "μ",
        r"\pi": "π",
        r"\angle": "∠",
        r"\triangle": "△",
        r"\parallel": "∥",
        r"\perp": "⟂",
        r"\because": "∵",
        r"\therefore": "∴",
        r"\leqslant": "≤",
        r"\geqslant": "≥",
        r"\leq": "≤",
        r"\geq": "≥",
        r"\times": "×",
        r"\div": "÷",
        r"\cdot": "·",
        r"\quad": " ",
        r"\qquad": "  ",
    }
    for k, v in replacements.items():
        s = s.replace(k, v)

    s = re.sub(r"\^\{\s*°\s*\}", "°", s)
    s = re.sub(r"\^\{\s*\\circ\s*\}", "°", s)
    s = re.sub(r"\{\s*\\circ\s*\}", "°", s)
    s = re.sub(r"\\circ", "°", s)
    s = re.sub(r"\^\{([^{}]+)\}", r"^\1", s)

    s = s.replace("{", "").replace("}", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def render_text_block(block: str):
    clean = sanitize_math_text(block)
    if not clean:
        return

    readable = latex_to_readable_text(clean)

    try:
        st.markdown(readable.replace("\n", "  \n"))
    except Exception:
        st.write(readable)


def render_rich_text(text: str, label: str = ""):
    raw = text or ""
    if not str(raw).strip():
        st.caption("暂无内容")
        return

    blocks = re.split(r"\n\s*\n", str(raw).strip())
    for block in blocks:
        render_text_block(block)


# =========================
# 图片
# =========================
def resolve_media_path(raw_path: str):
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



def render_images(image_list):
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
def get_saved_records_key(teacher_key: str):
    return f"saved_records::{teacher_key}"



def get_drafts_key(teacher_key: str):
    return f"drafts::{teacher_key}"



def get_index_key(teacher_key: str):
    return f"current_index::{teacher_key}"



def get_meta_key(teacher_key: str):
    return f"meta::{teacher_key}"



def get_current_saved_records():
    return st.session_state[get_saved_records_key(st.session_state["teacher_key"])]



def set_current_saved_records(records):
    st.session_state[get_saved_records_key(st.session_state["teacher_key"])] = records



def get_current_drafts():
    return st.session_state[get_drafts_key(st.session_state["teacher_key"])]



def set_current_drafts(drafts):
    st.session_state[get_drafts_key(st.session_state["teacher_key"])] = drafts



def get_current_index():
    return st.session_state[get_index_key(st.session_state["teacher_key"])]



def set_current_index(index: int):
    records = get_current_saved_records()
    total = len(records)
    index = 0 if total == 0 else max(0, min(index, total - 1))
    st.session_state[get_index_key(st.session_state["teacher_key"])] = index
    st.session_state["needs_state_sync"] = True



def get_current_meta() -> dict:
    return st.session_state[get_meta_key(st.session_state["teacher_key"])]



def set_current_meta(meta: dict):
    st.session_state[get_meta_key(st.session_state["teacher_key"])] = meta



def init_session():
    teacher_key = get_query_teacher()
    active_teacher = st.session_state.get("_active_teacher")

    if active_teacher != teacher_key:
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
# 草稿与保存
# =========================
def get_current_record_and_uid():
    idx = get_current_index()
    records = get_current_saved_records()
    record = records[idx]
    uid = get_record_uid(record, idx + 1)
    return idx, record, uid



def draft_equals_saved(annotation: dict, record: dict) -> bool:
    return normalize_annotation(annotation) == extract_saved_annotation(record)



def save_drafts_to_disk():
    teacher_key = st.session_state["teacher_key"]
    write_json_atomic(get_drafts_path(teacher_key), get_current_drafts())



def save_records_to_disk():
    teacher_key = st.session_state["teacher_key"]
    write_json_atomic(get_saved_records_path(teacher_key), get_current_saved_records())



def load_annotation_into_widgets(annotation: dict):
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
    st.session_state["edit_comment_bloom"] = annotation.get("human_comment_bloom", "")
    st.session_state["edit_comment_core"] = annotation.get("human_comment_core", "")

    st.session_state["suppress_draft_callbacks"] = False



def sync_widget_state(record: dict, uid: str):
    if not st.session_state.get("needs_state_sync", True):
        return

    drafts = get_current_drafts()
    annotation = drafts.get(uid) or extract_saved_annotation(record)
    load_annotation_into_widgets(annotation)
    st.session_state["needs_state_sync"] = False



def persist_current_draft_from_widgets():
    if st.session_state.get("suppress_draft_callbacks", False):
        return
    if "teacher_key" not in st.session_state:
        return
    if "edit_bloom" not in st.session_state:
        return

    idx, record, uid = get_current_record_and_uid()
    _ = idx
    annotation = build_annotation_from_widgets()
    drafts = deepcopy(get_current_drafts())
    meta = deepcopy(get_current_meta())

    if draft_equals_saved(annotation, record):
        drafts.pop(uid, None)
    else:
        drafts[uid] = {
            **annotation,
            "draft_updated_at": current_time_str(),
        }

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



def get_record_title(i: int, record: dict) -> str:
    uid = get_record_uid(record, i + 1)
    drafts = get_current_drafts()
    if uid in drafts:
        status = "📝"
    elif current_is_done(record):
        status = "✅"
    else:
        status = "⬜"
    return f"{status} 第{i + 1}题 · {uid}"



def make_export_name(teacher_key: str):
    t = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{teacher_key}_annotations_{t}.json"


# =========================
# 页面渲染
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

    done_count = sum(1 for x in records if current_is_done(x))
    draft_count = len(drafts)
    st.metric("总题数", total)
    st.metric("已保存", done_count)
    st.metric("未保存", total - done_count)
    st.metric("暂存草稿", draft_count)
    st.progress(done_count / total if total else 0.0)
    st.caption("✅ 已保存　📝 有暂存未保存　⬜ 未开始")

    if meta.get("last_commit_saved_at"):
        st.caption(f"最近正式保存：{meta['last_commit_saved_at']}")
    if meta.get("last_draft_saved_at"):
        st.caption(f"最近草稿暂存：{meta['last_draft_saved_at']}")

    st.divider()
    only_unfinished = st.checkbox("只看未保存题", value=False)

    visible_indices = [
        i for i, r in enumerate(records)
        if (not only_unfinished) or (not current_is_done(r))
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
            unfinished = [i for i, x in enumerate(records) if not current_is_done(x)]
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

saved_annotation = extract_saved_annotation(record)
current_widget_annotation = build_annotation_from_widgets()
has_unsaved_draft = not draft_equals_saved(current_widget_annotation, record)


top1, top2, top3, top4 = st.columns([1, 1, 1, 1])
with top1:
    if st.button("⬅ 上一题", disabled=(idx == 0), use_container_width=True):
        move(-1)
        st.rerun()
with top2:
    if st.button("下一题 ➡", disabled=(idx == total - 1), use_container_width=True):
        move(1)
        st.rerun()
with top3:
    if st.button("保存并下一题", use_container_width=True, type="primary"):
        save_current_record(show_toast=True)
        if idx < total - 1:
            set_current_index(idx + 1)
        st.rerun()
with top4:
    st.info(f"{teacher_label}：第 {idx + 1} / {total} 题")

left, right = st.columns([1.7, 1], gap="large")

with left:
    st.markdown("## 题目区")
    with st.container(height=980, border=True):
        st.markdown(f"**题目ID：** `{uid}`")
        st.markdown(f"**题型：** {record.get('type', '')}")
        if record.get("difficulty"):
            st.markdown(f"**难度：** {record.get('difficulty', '')}")
        if record.get("grades"):
            st.markdown(f"**年级：** {'、'.join(record.get('grades', []))}")

        st.markdown("### 题干")
        render_rich_text(record.get("normalized_stem") or record.get("stem", ""), label="题干")

        if record.get("stem_images"):
            st.markdown("### 题干图片")
            render_images(record.get("stem_images", []))

        if record.get("options"):
            st.markdown("### 选项")
            for option in record.get("options", []):
                option_text = f"**{option.get('index', '')}.** {option.get('text', '')}"
                render_rich_text(option_text, label=f"选项{option.get('index', '')}")
                if option.get("images"):
                    render_images(option.get("images", []))

        st.markdown("### 参考答案")
        render_rich_text(str(record.get("answer", "")), label="答案")

        st.markdown("### 解析")
        render_rich_text(record.get("normalized_analysis") or record.get("analysis", ""), label="解析")

        if record.get("analysis_images"):
            st.markdown("### 解析图片")
            render_images(record.get("analysis_images", []))

with right:
    saved_status = get_saved_status_text(record)
    draft_status = "有未保存修改" if has_unsaved_draft else "当前内容已与保存记录同步"
    st.markdown(f"<div class='status-line'>保存状态：{saved_status}｜当前状态：{draft_status}</div>", unsafe_allow_html=True)

    with st.container(border=True):
        model_bloom = record.get("bloom_level", "") or "无"
        model_primary = record.get("core_literacy_primary", "") or "无"
        model_candidates = record.get("core_literacy_candidates", []) or []
        model_candidates_text = "、".join(model_candidates) if model_candidates else "无"

        st.markdown("### 模型建议")
        st.markdown(f"**Bloom：** {model_bloom}")
        st.markdown(f"**核心素养主标签：** {model_primary}")
        st.markdown(f"**核心素养候选：** {model_candidates_text}")

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
            height=80,
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
            height=80,
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
