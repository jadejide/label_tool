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
AUTOSAVE_DIR = BASE_DIR / ".autosave"

# =========================
# 样式
# =========================
st.markdown("""
<style>
.block-container {
    padding-top: 2.2rem !important;
    padding-bottom: 1.5rem !important;
    max-width: 96rem;
}
h1 {
    font-size: 2.4rem !important;
    margin-bottom: 0.4rem !important;
}
h2 {
    font-size: 1.75rem !important;
}
h3 {
    font-size: 1.35rem !important;
}
p, li, div, label, span {
    font-size: 1.05rem !important;
}
[data-testid="stMarkdownContainer"] p {
    line-height: 1.65;
}
.small-muted {
    color: #666;
    font-size: 0.95rem !important;
}
.panel-title {
    margin-top: 0.1rem;
    margin-bottom: 0.6rem;
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

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    data = json.loads(text)
    if not isinstance(data, list):
        st.error("数据文件必须是 JSON 数组或 JSONL。")
        st.stop()
    return data


def dump_records_bytes(records):
    return json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")


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


def render_images(image_list, image_width: int):
    if not image_list:
        return
    for img in image_list:
        resolved = resolve_media_path(img)
        if resolved and resolved.exists():
            st.image(str(resolved), width=image_width)
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
    s = s.replace("\\vartriangle", "\\triangle")
    s = s.replace("vartriangle", "\\triangle")
    s = s.replace("\\left.", "").replace("\\right.", "")
    s = s.replace("\\left", "").replace("\\right", "")

    s = re.sub(r'(\d+)\s*\{\s*\\\\circ\s*\}', r'\1^\\circ', s)
    s = re.sub(r'(\d+)\s*\{\s*\\circ\s*\}', r'\1^\\circ', s)
    s = re.sub(r'(?<!\\)sqrt\s*([0-9a-zA-Z]+)', r'\\sqrt{\1}', s)
    s = re.sub(r'oversetbullet\s*([0-9a-zA-Z])', r'\\overset{\\bullet}{\1}', s)
    s = re.sub(r'(?<!\$)(\d+\s*\^\\circ)(?!\$)', r'$\1$', s)
    s = re.sub(r'[ \t]+', ' ', s)
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


def autosave_path_for(teacher_key: str) -> Path:
    return AUTOSAVE_DIR / f"{teacher_key}_autosave.json"


def ids_fingerprint(records):
    return [get_record_uid(r, i) for i, r in enumerate(records)]


def try_write_autosave(teacher_key: str, records):
    try:
        AUTOSAVE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "teacher_key": teacher_key,
            "saved_at": current_time_str(),
            "fingerprint": ids_fingerprint(records),
            "records": records,
        }
        autosave_path_for(teacher_key).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        st.session_state["last_autosave_ok"] = True
    except Exception as e:
        st.session_state["last_autosave_ok"] = False
        st.session_state["last_autosave_error"] = str(e)


def try_load_autosave(teacher_key: str, original_records):
    path = autosave_path_for(teacher_key)
    if not path.exists():
        return original_records, False

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        saved_records = payload.get("records", [])
        fingerprint = payload.get("fingerprint", [])
        if not isinstance(saved_records, list):
            return original_records, False
        if fingerprint and fingerprint == ids_fingerprint(original_records):
            return saved_records, True
        return original_records, False
    except Exception:
        return original_records, False


# =========================
# 状态管理
# =========================
def get_records_key(teacher_key: str):
    return f"records::{teacher_key}"


def get_index_key(teacher_key: str):
    return f"current_index::{teacher_key}"


def init_session():
    teacher_key = get_query_teacher()
    records_key = get_records_key(teacher_key)
    index_key = get_index_key(teacher_key)

    if records_key not in st.session_state:
        original_records = load_json_records(BASE_DIR / TASK_MAP[teacher_key]["file"])
        loaded_records, loaded_from_autosave = try_load_autosave(teacher_key, original_records)
        st.session_state[records_key] = loaded_records
        st.session_state["loaded_from_autosave"] = loaded_from_autosave

    if index_key not in st.session_state:
        st.session_state[index_key] = 0

    if "needs_state_sync" not in st.session_state:
        st.session_state["needs_state_sync"] = True

    st.session_state["teacher_key"] = teacher_key


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


def move(delta: int):
    set_current_index(get_current_index() + delta)


# =========================
# 编辑器逻辑
# =========================
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


def request_apply_model():
    st.session_state["pending_apply_model"] = True


def apply_model_if_needed(record: dict):
    if not st.session_state.get("pending_apply_model", False):
        return

    model_bloom = record.get("bloom_level")
    model_primary = record.get("core_literacy_primary")
    model_candidates = record.get("core_literacy_candidates", [])

    st.session_state["edit_bloom"] = model_bloom if model_bloom in BLOOM_LEVELS else BLOOM_LEVELS[0]
    st.session_state["edit_primary"] = model_primary if model_primary in CORE_LITERACIES else CORE_LITERACIES[0]
    st.session_state["edit_candidates"] = ensure_candidates_include_primary(
        st.session_state["edit_primary"], model_candidates
    )
    st.session_state["edit_accept"] = True
    st.session_state["pending_apply_model"] = False
    st.session_state["model_apply_feedback"] = "已同步大模型建议到标注区。"


def save_current_record(show_toast: bool = True):
    teacher_key = st.session_state["teacher_key"]
    idx = get_current_index()
    records = get_current_records()

    record = deepcopy(records[idx])
    record["human_bloom_level"] = st.session_state["edit_bloom"]
    record["human_core_literacy_primary"] = st.session_state["edit_primary"]
    record["human_core_literacy_candidates"] = ensure_candidates_include_primary(
        st.session_state["edit_primary"], st.session_state["edit_candidates"]
    )
    record["human_accept_model"] = st.session_state["edit_accept"]
    record["human_comment_bloom"] = st.session_state.get("edit_comment_bloom", "").strip()
    record["human_comment_core"] = st.session_state.get("edit_comment_core", "").strip()
    record["human_annotator"] = teacher_key
    record["human_updated_at"] = current_time_str()
    record["human_status"] = "已标注" if st.session_state["edit_bloom"] and st.session_state["edit_primary"] else "未完成"

    records[idx] = record
    set_current_records(records)
    try_write_autosave(teacher_key, records)
    if show_toast:
        st.toast("已保存当前题", icon="✅")


def restore_saved_state(record: dict):
    bloom_val = record.get("human_bloom_level") or record.get("bloom_level")
    primary_val = record.get("human_core_literacy_primary") or record.get("core_literacy_primary")
    candidates_val = record.get("human_core_literacy_candidates") or record.get("core_literacy_candidates", [])

    st.session_state["edit_bloom"] = bloom_val if bloom_val in BLOOM_LEVELS else BLOOM_LEVELS[0]
    st.session_state["edit_primary"] = primary_val if primary_val in CORE_LITERACIES else CORE_LITERACIES[0]
    st.session_state["edit_candidates"] = ensure_candidates_include_primary(
        st.session_state["edit_primary"], candidates_val
    )
    st.session_state["edit_accept"] = bool(record.get("human_accept_model", False))
    st.session_state["edit_comment_bloom"] = record.get("human_comment_bloom", "")
    st.session_state["edit_comment_core"] = record.get("human_comment_core", "")
    st.session_state["restore_feedback"] = "已恢复到当前已保存状态。"


def on_accept_toggle():
    if st.session_state.get("edit_accept", False):
        request_apply_model()


def editor_differs_from_record(record: dict) -> bool:
    current_candidates = ensure_candidates_include_primary(
        st.session_state.get("edit_primary", ""),
        st.session_state.get("edit_candidates", []),
    )
    saved_candidates = ensure_candidates_include_primary(
        record.get("human_core_literacy_primary") or record.get("core_literacy_primary", ""),
        record.get("human_core_literacy_candidates") or record.get("core_literacy_candidates", []),
    )

    return any([
        st.session_state.get("edit_bloom", "") != (record.get("human_bloom_level") or record.get("bloom_level") or BLOOM_LEVELS[0]),
        st.session_state.get("edit_primary", "") != (record.get("human_core_literacy_primary") or record.get("core_literacy_primary") or CORE_LITERACIES[0]),
        current_candidates != saved_candidates,
        bool(st.session_state.get("edit_accept", False)) != bool(record.get("human_accept_model", False)),
        (st.session_state.get("edit_comment_bloom", "") or "").strip() != (record.get("human_comment_bloom", "") or "").strip(),
        (st.session_state.get("edit_comment_core", "") or "").strip() != (record.get("human_comment_core", "") or "").strip(),
    ])


# =========================
# 页面
# =========================
init_session()

teacher_key = st.session_state["teacher_key"]
teacher_label = TASK_MAP[teacher_key]["label"]
records = get_current_records()
total = len(records)

st.title("数字题人工标注工具")
st.caption("左侧题目区和右侧标注区使用独立滚动容器，避免长题来回拖动。")

with st.sidebar:
    st.subheader("当前任务")
    st.write(f"**任务：** {teacher_label}")
    st.write(f"**参数：** `{teacher_key}`")

    panel_height = st.slider("左右面板高度", min_value=520, max_value=980, value=760, step=20)
    image_width = st.slider("图片显示宽度", min_value=220, max_value=700, value=360, step=20)

    done_count = sum(1 for x in records if current_is_done(x))
    st.metric("总题数", total)
    st.metric("已完成", done_count)
    st.metric("未完成", total - done_count)
    st.progress(done_count / total if total else 0.0)

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
            set_current_index(jump_index)
            st.rerun()

        if st.button("跳到下一道未完成题", use_container_width=True):
            unfinished = [i for i, x in enumerate(records) if not current_is_done(x)]
            if unfinished:
                current = get_current_index()
                target = next((i for i in unfinished if i > current), unfinished[0])
                set_current_index(target)
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

if st.session_state.get("loaded_from_autosave"):
    st.info("已恢复本地自动保存进度。注意：云端重启或重新部署后，这类自动保存不一定保留。")

idx = get_current_index()
record = records[idx]
sync_widget_state(record)
apply_model_if_needed(record)

top1, top2, top3, top4 = st.columns([1, 1, 1, 0.9])
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
        save_current_record(show_toast=False)
        if idx < total - 1:
            move(1)
        st.rerun()
with top4:
    st.info(f"{idx + 1} / {total}")

left, right = st.columns([1.78, 1], gap="large")

with left:
    st.markdown('<div class="panel-title"><h2>题目区</h2></div>', unsafe_allow_html=True)
    with st.container(height=panel_height, border=True):
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
            render_images(record.get("stem_images", []), image_width=image_width)

        if record.get("options"):
            st.markdown("### 选项")
            for option in record.get("options", []):
                render_rich_text(
                    f"**{option.get('index', '')}.** {option.get('text', '')}",
                    label=f"选项{option.get('index', '')}",
                )
                if option.get("images"):
                    render_images(option.get("images", []), image_width=image_width)

        st.markdown("### 参考答案")
        render_rich_text(str(record.get("answer", "")), label="答案")

        st.markdown("### 解析")
        render_rich_text(record.get("normalized_analysis") or record.get("analysis", ""), label="解析")

        if record.get("analysis_images"):
            st.markdown("### 解析图片")
            render_images(record.get("analysis_images", []), image_width=image_width)

with right:
    st.markdown('<div class="panel-title"><h2>标注区</h2></div>', unsafe_allow_html=True)
    with st.container(height=panel_height, border=True):
        if editor_differs_from_record(record):
            st.warning("当前右侧有未保存修改。")
        else:
            st.success("当前题修改已保存。")

        if st.session_state.get("model_apply_feedback"):
            st.info(st.session_state["model_apply_feedback"])
            st.session_state["model_apply_feedback"] = ""
        if st.session_state.get("restore_feedback"):
            st.info(st.session_state["restore_feedback"])
            st.session_state["restore_feedback"] = ""

        with st.container(border=True):
            st.markdown("### Bloom 标注")
            st.caption(f"模型建议：{record.get('bloom_level', '无') or '无'}")
            st.radio(
                "Bloom 层级",
                options=BLOOM_LEVELS,
                key="edit_bloom",
                horizontal=True,
                label_visibility="collapsed",
            )
            st.text_area("Bloom 备注", key="edit_comment_bloom", height=100)

        st.write("")

        with st.container(border=True):
            st.markdown("### 核心素养标注")
            model_primary = record.get("core_literacy_primary", "无") or "无"
            model_candidates = ", ".join(record.get("core_literacy_candidates", [])) if record.get("core_literacy_candidates") else "无"
            st.caption(f"模型主标签：{model_primary}")
            st.caption(f"模型候选：{model_candidates}")
            st.selectbox("核心素养主标签", options=CORE_LITERACIES, key="edit_primary")
            st.multiselect("核心素养候选（最多 3 个）", options=CORE_LITERACIES, key="edit_candidates", max_selections=3)
            st.checkbox(
                "采纳大模型建议（勾选会自动同步标签）",
                key="edit_accept",
                on_change=on_accept_toggle,
            )
            st.text_area("核心素养备注", key="edit_comment_core", height=100)

        st.write("")

        row1, row2, row3 = st.columns(3)
        with row1:
            if st.button("保存当前题", use_container_width=True):
                save_current_record(show_toast=True)
                st.rerun()
        with row2:
            if st.button("恢复到已保存状态", use_container_width=True):
                restore_saved_state(record)
                st.rerun()
        with row3:
            if st.button("填入模型建议", use_container_width=True):
                request_apply_model()
                st.rerun()

        st.write("")

        row4, row5 = st.columns(2)
        with row4:
            if st.button("跳过本题", use_container_width=True):
                if idx < total - 1:
                    move(1)
                st.rerun()
        with row5:
            if st.button("清空两类备注", use_container_width=True):
                st.session_state["edit_comment_bloom"] = ""
                st.session_state["edit_comment_core"] = ""
                st.rerun()

        if st.session_state.get("last_autosave_ok") is False:
            st.caption(f"自动保存失败：{st.session_state.get('last_autosave_error', '')}")
        else:
            st.markdown(
                '<div class="small-muted">“填入模型建议”会把模型的 Bloom、主标签和候选标签写入当前标注区；“恢复到已保存状态”会撤销你当前未保存的改动。</div>',
                unsafe_allow_html=True,
            )
