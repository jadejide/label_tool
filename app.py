import json
from pathlib import Path
from datetime import datetime
from copy import deepcopy

import streamlit as st

st.set_page_config(page_title="数学题人工标注工具", layout="wide")

# =========================
# 基础配置
# =========================
BLOOM_LEVELS = ["记忆", "理解", "应用", "分析", "评价", "创造"]
CORE_LITERACIES = [
    "抽象能力", "运算能力", "几何直观", "空间观念", "推理能力",
    "数据观念", "模型观念", "应用意识", "创新意识",
]

# 统一使用 teacher1 / teacher2 / teacher3
TASK_MAP = {
    "teacher1": {"label": "teacher1", "file": "data/teacher1.json"},
    "teacher2": {"label": "teacher2", "file": "data/teacher2.json"},
    "teacher3": {"label": "teacher3", "file": "data/teacher3.json"},
}

# 建议保持 False：老师只访问自己的链接
ALLOW_TASK_SWITCH = False

BASE_DIR = Path(__file__).parent


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


def set_query_teacher(teacher_key: str):
    st.query_params["teacher"] = teacher_key


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
            st.image(str(resolved), use_container_width=True)
        else:
            st.caption(f"图片文件未找到：{img}")


def render_rich_text(text: str):
    st.markdown((text or "").replace("\n", "  \n"))


def build_annotated_record(record, annotator_name, bloom_value, primary_value, candidates_value, accept_model, comment):
    new_record = deepcopy(record)
    candidates_value = ensure_candidates_include_primary(primary_value, candidates_value)

    new_record["human_bloom_level"] = bloom_value
    new_record["human_core_literacy_primary"] = primary_value
    new_record["human_core_literacy_candidates"] = candidates_value
    new_record["human_accept_model"] = bool(accept_model)
    new_record["human_comment"] = comment.strip()
    new_record["human_annotator"] = annotator_name
    new_record["human_updated_at"] = current_time_str()
    new_record["human_status"] = "已标注" if bloom_value and primary_value else "未完成"
    return new_record


def make_export_name(teacher_key: str):
    t = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{teacher_key}_annotations_{t}.json"


# =========================
# 会话状态
# =========================
def get_records_state_key(teacher_key: str) -> str:
    return f"records::{teacher_key}"


def get_index_state_key(teacher_key: str) -> str:
    return f"current_index::{teacher_key}"


def init_session():
    teacher_key = get_query_teacher()
    records_key = get_records_state_key(teacher_key)
    index_key = get_index_state_key(teacher_key)

    if records_key not in st.session_state:
        file_path = BASE_DIR / TASK_MAP[teacher_key]["file"]
        st.session_state[records_key] = load_json_records(file_path)

    if index_key not in st.session_state:
        st.session_state[index_key] = 0

    st.session_state["teacher_key"] = teacher_key


def get_current_records():
    teacher_key = st.session_state["teacher_key"]
    return st.session_state[get_records_state_key(teacher_key)]


def set_current_records(records):
    teacher_key = st.session_state["teacher_key"]
    st.session_state[get_records_state_key(teacher_key)] = records


def get_current_index():
    teacher_key = st.session_state["teacher_key"]
    return st.session_state[get_index_state_key(teacher_key)]


def set_current_index(index: int):
    teacher_key = st.session_state["teacher_key"]
    records = get_current_records()
    total = len(records)

    if total == 0:
        st.session_state[get_index_state_key(teacher_key)] = 0
    else:
        st.session_state[get_index_state_key(teacher_key)] = max(0, min(index, total - 1))


def move(delta: int):
    set_current_index(get_current_index() + delta)


# =========================
# 表单状态同步
# =========================
def hydrate_form_state(record: dict, idx: int):
    record_uid = get_record_uid(record, idx)
    record_signature = f"{st.session_state['teacher_key']}::{record_uid}"

    if st.session_state.get("form_record_signature") == record_signature:
        return

    model_bloom = record.get("bloom_level", "")
    model_primary = record.get("core_literacy_primary", "")
    model_candidates = record.get("core_literacy_candidates", [])

    bloom_value = record.get("human_bloom_level") or model_bloom
    if bloom_value not in BLOOM_LEVELS:
        bloom_value = BLOOM_LEVELS[0]

    primary_value = record.get("human_core_literacy_primary") or model_primary
    if primary_value not in CORE_LITERACIES:
        primary_value = CORE_LITERACIES[0]

    candidates_value = record.get("human_core_literacy_candidates") or model_candidates
    candidates_value = ensure_candidates_include_primary(primary_value, candidates_value)

    st.session_state["form_bloom"] = bloom_value
    st.session_state["form_primary"] = primary_value
    st.session_state["form_candidates"] = candidates_value
    st.session_state["form_accept_model"] = bool(record.get("human_accept_model", False))
    st.session_state["form_comment"] = record.get("human_comment", "")
    st.session_state["form_record_signature"] = record_signature


def save_current_record(stay_on_page: bool = True):
    teacher_key = st.session_state["teacher_key"]
    records = get_current_records()
    idx = get_current_index()
    record = records[idx]

    updated = build_annotated_record(
        record=record,
        annotator_name=teacher_key,
        bloom_value=st.session_state["form_bloom"],
        primary_value=st.session_state["form_primary"],
        candidates_value=st.session_state["form_candidates"],
        accept_model=st.session_state["form_accept_model"],
        comment=st.session_state["form_comment"],
    )

    records[idx] = updated
    set_current_records(records)

    if not stay_on_page:
        move(1)

    st.toast("已保存", icon="✅")


def reset_form_to_model(record: dict, idx: int):
    model_bloom = record.get("bloom_level") if record.get("bloom_level") in BLOOM_LEVELS else BLOOM_LEVELS[0]
    model_primary = record.get("core_literacy_primary") if record.get("core_literacy_primary") in CORE_LITERACIES else CORE_LITERACIES[0]
    model_candidates = ensure_candidates_include_primary(model_primary, record.get("core_literacy_candidates", []))

    st.session_state["form_bloom"] = model_bloom
    st.session_state["form_primary"] = model_primary
    st.session_state["form_candidates"] = model_candidates
    st.session_state["form_accept_model"] = False
    st.session_state["form_comment"] = ""
    st.session_state["form_record_signature"] = f"{st.session_state['teacher_key']}::{get_record_uid(record, idx)}"


# =========================
# 页面
# =========================
init_session()

teacher_key = st.session_state["teacher_key"]
teacher_label = TASK_MAP[teacher_key]["label"]
records = get_current_records()
total = len(records)

st.title("数学题人工标注工具")
st.caption("老师通过自己的链接进入，参考大模型建议后进行人工修订，最后下载结果 JSON。")

with st.sidebar:
    st.subheader("当前任务")
    st.write(f"**任务：** {teacher_label}")
    st.write(f"**参数：** `{teacher_key}`")

    if ALLOW_TASK_SWITCH:
        task_labels = list(TASK_MAP.keys())
        selected_task = st.selectbox("切换任务", task_labels, index=task_labels.index(teacher_key))
        if selected_task != teacher_key:
            set_query_teacher(selected_task)
            st.rerun()

    done_count = sum(1 for x in records if current_is_done(x))
    st.metric("总题数", total)
    st.metric("已完成", done_count)
    st.metric("未完成", total - done_count)
    st.progress(done_count / total if total else 0.0)

    st.divider()
    st.subheader("快速跳转")

    only_unfinished = st.checkbox("只看未完成题", value=False)

    visible_indices = [
        i for i, r in enumerate(records)
        if (not only_unfinished) or (not current_is_done(r))
    ]

    if visible_indices:
        title_map = {get_record_title(i, records[i]): i for i in visible_indices}
        titles = list(title_map.keys())

        current_index = get_current_index()
        default_position = visible_indices.index(current_index) if current_index in visible_indices else 0

        selected_title = st.selectbox(
            "题目列表",
            titles,
            index=default_position,
            key=f"jump_selectbox::{teacher_key}",
        )
        jump_index = title_map[selected_title]
        if jump_index != current_index:
            set_current_index(jump_index)
            st.rerun()

        if st.button("跳到下一道未完成题", use_container_width=True):
            unfinished = [i for i, x in enumerate(records) if not current_is_done(x)]
            if unfinished:
                current = get_current_index()
                target = None
                for i in unfinished:
                    if i > current:
                        target = i
                        break
                if target is None:
                    target = unfinished[0]
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

idx = get_current_index()
record = records[idx]
hydrate_form_state(record, idx)

st.subheader(f"{teacher_label}：第 {idx + 1} / {total} 题")

nav1, nav2, nav3, nav4 = st.columns([1, 1, 1, 3])
with nav1:
    if st.button("⬅ 上一题", disabled=(idx == 0), use_container_width=True):
        move(-1)
        st.rerun()
with nav2:
    if st.button("下一题 ➡", disabled=(idx == total - 1), use_container_width=True):
        move(1)
        st.rerun()
with nav3:
    if st.button("跳过本题", use_container_width=True):
        move(1)
        st.rerun()
with nav4:
    if current_is_done(record):
        st.success("本题已完成")
    else:
        st.warning("本题未完成")

left, right = st.columns([1.35, 1])

with left:
    st.markdown("### 题目信息")
    st.markdown(f"**题目ID：** `{get_record_uid(record, idx)}`")
    st.markdown(f"**题型：** {record.get('type', '')}")
    if record.get("difficulty"):
        st.markdown(f"**难度：** {record.get('difficulty', '')}")
    if record.get("grades"):
        st.markdown(f"**年级：** {'、'.join(record.get('grades', []))}")

    st.markdown("#### 题干")
    render_rich_text(record.get("normalized_stem") or record.get("stem", ""))

    if record.get("stem_images"):
        st.markdown("#### 题干图片")
        render_images(record.get("stem_images", []))

    if record.get("options"):
        st.markdown("#### 选项")
        for option in record.get("options", []):
            st.markdown(f"**{option.get('index', '')}.** {option.get('text', '')}")
            if option.get("images"):
                render_images(option.get("images", []))

    st.markdown("#### 参考答案")
    render_rich_text(str(record.get("answer", "")))

    st.markdown("#### 解析")
    render_rich_text(record.get("normalized_analysis") or record.get("analysis", ""))

    if record.get("analysis_images"):
        st.markdown("#### 解析图片")
        render_images(record.get("analysis_images", []))

with right:
    st.markdown("### 大模型建议")
    st.markdown(
        f"""
**Bloom 层级：** {record.get('bloom_level', '无') or '无'}  
**Bloom 原因：** {record.get('bloom_reason', '无') or '无'}  

**核心素养主标签：** {record.get('core_literacy_primary', '无') or '无'}  
**核心素养候选：** {", ".join(record.get('core_literacy_candidates', [])) if record.get('core_literacy_candidates') else '无'}  
**核心素养原因：** {record.get('core_literacy_reason', '无') or '无'}
"""
    )

    st.markdown("### 人工标注")
    with st.form("annotation_form", clear_on_submit=False):
        st.radio("Bloom 层级", options=BLOOM_LEVELS, key="form_bloom", horizontal=True)
        st.selectbox("核心素养主标签", options=CORE_LITERACIES, key="form_primary")
        st.multiselect("核心素养候选（最多 3 个）", options=CORE_LITERACIES, key="form_candidates", max_selections=3)
        st.checkbox("采纳大模型建议", key="form_accept_model")
        st.text_area("备注", key="form_comment", height=120)

        c1, c2, c3 = st.columns(3)
        save_now = c1.form_submit_button("保存当前题", use_container_width=True)
        save_next = c2.form_submit_button("保存并下一题", use_container_width=True)
        reset_model = c3.form_submit_button("恢复模型建议", use_container_width=True)

    if reset_model:
        reset_form_to_model(record, idx)
        st.rerun()

    if save_now:
        save_current_record(stay_on_page=True)
        st.rerun()

    if save_next:
        save_current_record(stay_on_page=False)
        st.rerun()

    st.divider()
    st.markdown("### 当前人工结果")
    preview = get_current_records()[get_current_index()]
    st.json({
        "human_bloom_level": preview.get("human_bloom_level", ""),
        "human_core_literacy_primary": preview.get("human_core_literacy_primary", ""),
        "human_core_literacy_candidates": preview.get("human_core_literacy_candidates", []),
        "human_accept_model": preview.get("human_accept_model", False),
        "human_comment": preview.get("human_comment", ""),
        "human_status": preview.get("human_status", "未完成"),
        "human_updated_at": preview.get("human_updated_at", ""),
    })
