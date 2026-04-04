import json
import re
from pathlib import Path
from datetime import datetime
from copy import deepcopy

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
TASK_MAP = {
    "teacher1": {"label": "teacher1", "file": "data/teacher1.json"},
    "teacher2": {"label": "teacher2", "file": "data/teacher2.json"},
    "teacher3": {"label": "teacher3", "file": "data/teacher3.json"},
}
BASE_DIR = Path(__file__).parent

# =========================
# 样式
# =========================
st.markdown("""
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
</style>
""", unsafe_allow_html=True)

# =========================
# 工具函数
# =========================
def load_json_records(path: Path):
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
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        data = json.loads(text)
    except json.JSONDecodeError as e:
        st.error(f"JSON 解析失败：{path}\n{e}")
        st.stop()

    if not isinstance(data, list):
        st.error("数据文件必须是 JSON 数组或 JSONL。")
        st.stop()

    return data

def dump_records_bytes(records):
    return json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")

def get_autosave_path(teacher_key: str) -> Path:
    save_dir = BASE_DIR / "data"
    save_dir.mkdir(parents=True, exist_ok=True)
    return save_dir / f"{teacher_key}_autosave.json"

def auto_save_to_disk():
    teacher_key = st.session_state["teacher_key"]
    records = st.session_state[get_records_key(teacher_key)]
    save_path = get_autosave_path(teacher_key)
    try:
        save_path.write_bytes(dump_records_bytes(records))
        st.session_state["last_saved_at"] = current_time_str()
    except Exception as e:
        st.warning(f"自动保存失败：{e}")

def get_query_teacher():
    teacher = st.query_params.get("teacher", "teacher1")
    if isinstance(teacher, list):
        teacher = teacher[0] if teacher else "teacher1"
    teacher = str(teacher).strip()
    if teacher not in TASK_MAP:
        teacher = "teacher1"
    return teacher

def current_time_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_record_uid(record: dict, idx: int) -> str:
    return str(record.get("id") or record.get("sample_id") or f"item_{idx}")

def current_is_done(record: dict) -> bool:
    return bool(record.get("human_bloom_level")) and bool(record.get("human_core_literacy_primary"))

def get_record_title(i: int, record: dict) -> str:
    qid = get_record_uid(record, i + 1)
    status = "✅" if current_is_done(record) else "⬜"
    return f"{status} 第{i + 1}题 · {qid}"

def ensure_candidates_include_primary(primary, candidates):
    clean = []
    for x in candidates or []:
        if x in CORE_LITERACIES and x not in clean:
            clean.append(x)

    if primary in CORE_LITERACIES:
        if primary in clean:
            clean.remove(primary)
        clean = [primary] + clean

    return clean[:3]

def resolve_media_path(raw_path: str):
    if not raw_path:
        return None
    p = Path(raw_path)
    candidates = [
        BASE_DIR / p,
        BASE_DIR / "images" / p.name,
        BASE_DIR / "image" / p.name,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None

def render_images(image_list):
    if not image_list:
        return
    for img in image_list:
        resolved = resolve_media_path(img)
        if resolved and resolved.exists():
            st.image(str(resolved))
        else:
            st.caption(f"图片文件未找到：{img}")

def sanitize_math_text(text: str) -> str:
    if not text:
        return ""
    s = str(text)
    s = s.replace("\\(", "$").replace("\\)", "$")
    s = s.replace("\\[", "$$").replace("\\]", "$$")
    s = s.replace("⩽", "\\leqslant")
    s = s.replace("⩾", "\\geqslant")
    s = s.replace("{^\\circ}", "^{\\circ}")
    s = s.replace("{\\circ}", "^{\\circ}")
    s = re.sub(r'(\d+)\s*\{\s*\\\\circ\s*\}', r'\1^{\\circ}', s)
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'(?<!\$)(\d+\^\{\\circ\})(?!\$)', r'$\1$', s)
    return s.strip()

def render_rich_text(text: str, label: str = ""):
    raw = text or ""
    clean = sanitize_math_text(raw)
    try:
        st.markdown(clean.replace("\n", "  \n"))
    except Exception:
        st.code(raw, language="text")
        return
    if clean != raw:
        with st.expander(f"查看原始{label or '文本'}", expanded=False):
            st.code(raw, language="text")

def make_export_name(teacher_key: str):
    t = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{teacher_key}_annotations_{t}.json"

# =========================
# 会话与状态管理
# =========================
def get_records_key(teacher_key: str):
    return f"records::{teacher_key}"

def get_index_key(teacher_key: str):
    return f"current_index::{teacher_key}"

def mark_dirty():
    st.session_state["is_dirty"] = True

def on_primary_change():
    primary = st.session_state.get("edit_primary")
    candidates = st.session_state.get("edit_candidates", [])
    st.session_state["edit_candidates"] = ensure_candidates_include_primary(primary, candidates)
    mark_dirty()

def on_candidates_change():
    primary = st.session_state.get("edit_primary")
    candidates = st.session_state.get("edit_candidates", [])
    st.session_state["edit_candidates"] = ensure_candidates_include_primary(primary, candidates)
    mark_dirty()

def init_session():
    teacher_key = get_query_teacher()
    prev_teacher = st.session_state.get("_active_teacher")

    if prev_teacher != teacher_key:
        st.session_state["needs_state_sync"] = True

    records_key = get_records_key(teacher_key)
    index_key = get_index_key(teacher_key)

    autosave_path = get_autosave_path(teacher_key)
    original_path = BASE_DIR / TASK_MAP[teacher_key]["file"]

    if records_key not in st.session_state:
        if autosave_path.exists():
            st.session_state[records_key] = load_json_records(autosave_path)
            st.toast("已加载上次未完成的自动保存记录", icon="📝")
        else:
            st.session_state[records_key] = load_json_records(original_path)

    if index_key not in st.session_state:
        st.session_state[index_key] = 0

    st.session_state["teacher_key"] = teacher_key
    st.session_state["_active_teacher"] = teacher_key
    st.session_state.setdefault("needs_state_sync", True)
    st.session_state.setdefault("is_dirty", False)
    st.session_state.setdefault("last_saved_at", "")

def get_current_records():
    return st.session_state[get_records_key(st.session_state["teacher_key"])]

def set_current_records(records):
    st.session_state[get_records_key(st.session_state["teacher_key"])] = records

def get_current_index():
    return st.session_state[get_index_key(st.session_state["teacher_key"])]

def set_current_index(index: int):
    records = get_current_records()
    total = len(records)
    index = 0 if total == 0 else max(0, min(index, total - 1))
    st.session_state[get_index_key(st.session_state["teacher_key"])] = index
    st.session_state["needs_state_sync"] = True
    st.session_state["is_dirty"] = False

def sync_widget_state(record: dict):
    if not st.session_state.get("needs_state_sync", True):
        return

    model_bloom = record.get("bloom_level", "")
    model_primary = record.get("core_literacy_primary", "")
    model_candidates = record.get("core_literacy_candidates", [])

    bloom_val = record.get("human_bloom_level") or model_bloom
    primary_val = record.get("human_core_literacy_primary") or model_primary
    candidates_val = record.get("human_core_literacy_candidates") or model_candidates

    if bloom_val not in BLOOM_LEVELS:
        bloom_val = BLOOM_LEVELS[0]
    if primary_val not in CORE_LITERACIES:
        primary_val = CORE_LITERACIES[0]

    st.session_state["edit_bloom"] = bloom_val
    st.session_state["edit_primary"] = primary_val
    st.session_state["edit_candidates"] = ensure_candidates_include_primary(primary_val, candidates_val)
    st.session_state["edit_accept"] = bool(record.get("human_accept_model", False))
    st.session_state["edit_comment_bloom"] = record.get("human_comment_bloom", "")
    st.session_state["edit_comment_core"] = record.get("human_comment_core", "")

    st.session_state["needs_state_sync"] = False
    st.session_state["is_dirty"] = False

def save_current_record(show_toast: bool = False):
    teacher_key = st.session_state["teacher_key"]
    idx = get_current_index()
    records = get_current_records()

    if not records:
        return

    record = deepcopy(records[idx])
    record["human_bloom_level"] = st.session_state.get("edit_bloom", "")
    record["human_core_literacy_primary"] = st.session_state.get("edit_primary", "")
    record["human_core_literacy_candidates"] = ensure_candidates_include_primary(
        st.session_state.get("edit_primary", ""),
        st.session_state.get("edit_candidates", []),
    )
    record["human_accept_model"] = st.session_state.get("edit_accept", False)
    record["human_comment_bloom"] = st.session_state.get("edit_comment_bloom", "").strip()
    record["human_comment_core"] = st.session_state.get("edit_comment_core", "").strip()
    record["human_annotator"] = teacher_key
    record["human_updated_at"] = current_time_str()
    record["human_status"] = (
        "已标注"
        if record["human_bloom_level"] and record["human_core_literacy_primary"]
        else "未完成"
    )

    records[idx] = record
    set_current_records(records)
    auto_save_to_disk()
    st.session_state["is_dirty"] = False

    if show_toast:
        st.toast("已保存", icon="✅")

def maybe_save_before_leave():
    if st.session_state.get("is_dirty", False):
        save_current_record()

def move(delta: int):
    maybe_save_before_leave()
    set_current_index(get_current_index() + delta)

def jump_to(index: int):
    maybe_save_before_leave()
    set_current_index(index)

def reset_to_model(record: dict):
    model_bloom = record.get("bloom_level")
    model_primary = record.get("core_literacy_primary")
    model_candidates = record.get("core_literacy_candidates", [])

    bloom_val = model_bloom if model_bloom in BLOOM_LEVELS else BLOOM_LEVELS[0]
    primary_val = model_primary if model_primary in CORE_LITERACIES else CORE_LITERACIES[0]

    st.session_state["edit_bloom"] = bloom_val
    st.session_state["edit_primary"] = primary_val
    st.session_state["edit_candidates"] = ensure_candidates_include_primary(primary_val, model_candidates)
    st.session_state["edit_accept"] = False
    st.session_state["edit_comment_bloom"] = ""
    st.session_state["edit_comment_core"] = ""
    st.session_state["is_dirty"] = True
    st.session_state["needs_state_sync"] = False

# =========================
# 页面渲染
# =========================
init_session()

teacher_key = st.session_state["teacher_key"]
teacher_label = TASK_MAP[teacher_key]["label"]
records = get_current_records()
total = len(records)

st.title("数字题人工标注工具")

with st.sidebar:
    st.subheader("当前任务")
    st.write(f"**任务：** {teacher_label}")
    st.write(f"**参数：** `{teacher_key}`")

    done_count = sum(1 for x in records if current_is_done(x))
    st.metric("总题数", total)
    st.metric("已完成", done_count)
    st.metric("未完成", total - done_count)
    st.progress(done_count / total if total else 0.0)

    if st.session_state.get("last_saved_at"):
        st.caption(f"最近自动保存：{st.session_state['last_saved_at']}")

    st.divider()
    only_unfinished = st.checkbox("只看未完成题", value=False)

    visible_indices = [i for i, r in enumerate(records) if (not only_unfinished) or (not current_is_done(r))]
    if visible_indices:
        title_map = {get_record_title(i, records[i]): i for i in visible_indices}
        titles = list(title_map.keys())
        current_index = get_current_index()
        default_position = visible_indices.index(current_index) if current_index in visible_indices else 0

        selected_title = st.selectbox("题目列表", titles, index=default_position)
        jump_index = title_map[selected_title]
        if jump_index != current_index:
            jump_to(jump_index)
            st.rerun()

        if st.button("跳到下一道未完成题", use_container_width=True):
            unfinished = [i for i, x in enumerate(records) if not current_is_done(x)]
            if unfinished:
                current = get_current_index()
                target = next((i for i in unfinished if i > current), unfinished[0])
                jump_to(target)
                st.rerun()
    else:
        st.success("当前任务已全部完成。")

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
sync_widget_state(record)

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
    with st.container(height=750, border=True):
        st.markdown(f"**题目ID：** `{get_record_uid(record, idx)}`")
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
                render_rich_text(
                    f"**{option.get('index', '')}.** {option.get('text', '')}",
                    label=f"选项{option.get('index', '')}"
                )
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
    with st.container(border=True):
        st.markdown("### Bloom 标注")
        st.caption(f"模型建议：{record.get('bloom_level', '无') or '无'}")
        st.radio(
            "Bloom 层级",
            options=BLOOM_LEVELS,
            key="edit_bloom",
            horizontal=True,
            label_visibility="collapsed",
            on_change=mark_dirty,
        )
        st.text_area("Bloom 备注", key="edit_comment_bloom", height=80, on_change=mark_dirty)

    st.write("")

    with st.container(border=True):
        st.markdown("### 核心素养标注")
        model_primary = record.get('core_literacy_primary', '无') or '无'
        model_candidates = ", ".join(record.get('core_literacy_candidates', [])) if record.get('core_literacy_candidates') else "无"
        st.caption(f"模型主标签：{model_primary}")
        st.caption(f"模型候选：{model_candidates}")

        st.selectbox(
            "核心素养主标签",
            options=CORE_LITERACIES,
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
        st.checkbox("采纳大模型建议", key="edit_accept", on_change=mark_dirty)
        st.text_area("核心素养备注", key="edit_comment_core", height=80, on_change=mark_dirty)

    st.write("")

    btn1, btn2, btn3 = st.columns(3)
    with btn1:
        if st.button("保存当前题", use_container_width=True):
            save_current_record(show_toast=True)
    with btn2:
        if st.button("恢复模型建议", use_container_width=True):
            reset_to_model(record)
            st.rerun()
    with btn3:
        if st.button("跳过本题", use_container_width=True):
            move(1)
            st.rerun()
