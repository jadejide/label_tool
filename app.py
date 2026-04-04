import json
from pathlib import Path
from datetime import datetime
from copy import deepcopy

import streamlit as st

st.set_page_config(page_title="数学题人工标注工具", layout="wide")

BLOOM_LEVELS = ["记忆", "理解", "应用", "分析", "评价", "创造"]
CORE_LITERACIES = [
    "抽象能力",
    "运算能力",
    "几何直观",
    "空间观念",
    "推理能力",
    "数据观念",
    "模型观念",
    "应用意识",
    "创新意识",
]

TASK_MAP = {
    "zhang": {"name": "张老师", "file": "data/teacher_zhang.json"},
    "li": {"name": "李老师", "file": "data/teacher_li.json"},
    "wang": {"name": "王老师", "file": "data/teacher_wang.json"},
}

BASE_DIR = Path(__file__).parent


def load_json_records(path: Path):
    if not path.exists():
        st.error(f"未找到数据文件：{path}")
        st.stop()

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


def save_download_bytes(records):
    return json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")


def get_query_teacher():
    teacher = st.query_params.get("teacher", "zhang")
    if teacher not in TASK_MAP:
        teacher = "zhang"
    return teacher


def set_query_teacher(teacher_key: str):
    st.query_params["teacher"] = teacher_key


def build_annotated_record(record, annotator_name, bloom_value, primary_value, candidates_value, accept_model, comment):
    new_record = deepcopy(record)
    new_record["human_bloom_level"] = bloom_value
    new_record["human_core_literacy_primary"] = primary_value
    new_record["human_core_literacy_candidates"] = candidates_value[:3]
    new_record["human_accept_model"] = bool(accept_model)
    new_record["human_comment"] = comment.strip()
    new_record["human_annotator"] = annotator_name
    new_record["human_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_record["human_status"] = "已标注" if bloom_value and primary_value else "未完成"
    return new_record


def current_is_done(record):
    return bool(record.get("human_bloom_level")) and bool(record.get("human_core_literacy_primary"))


def get_record_title(i, record):
    qid = record.get("id", f"item_{i+1}")
    status = "✅" if current_is_done(record) else "⬜"
    return f"{status} 第{i+1}题 · {qid}"


def render_images(image_list):
    if not image_list:
        return
    for img in image_list:
        img_path = BASE_DIR / img
        if img_path.exists():
            st.image(str(img_path), use_container_width=True)
        else:
            st.caption(f"图片文件未找到：{img}")


def ensure_candidates_include_primary(primary, candidates):
    clean = []
    for x in candidates:
        if x in CORE_LITERACIES and x not in clean:
            clean.append(x)
    if primary in CORE_LITERACIES:
        if primary in clean:
            clean.remove(primary)
        clean = [primary] + clean
    return clean[:3]


def init_session():
    teacher_key = get_query_teacher()

    if "teacher_key" not in st.session_state:
        st.session_state.teacher_key = teacher_key

    if st.session_state.teacher_key != teacher_key:
        st.session_state.teacher_key = teacher_key
        st.session_state.pop("records", None)
        st.session_state.pop("current_index", None)

    if "records" not in st.session_state:
        file_path = BASE_DIR / TASK_MAP[teacher_key]["file"]
        st.session_state.records = load_json_records(file_path)

    if "current_index" not in st.session_state:
        st.session_state.current_index = 0


def jump_to(index: int):
    total = len(st.session_state.records)
    if total == 0:
        st.session_state.current_index = 0
        return
    st.session_state.current_index = max(0, min(index, total - 1))


def move(delta: int):
    jump_to(st.session_state.current_index + delta)


def make_export_name(teacher_key: str):
    t = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{teacher_key}_annotations_{t}.json"


init_session()

teacher_key = st.session_state.teacher_key
teacher_name = TASK_MAP[teacher_key]["name"]
records = st.session_state.records
total = len(records)

st.title("数学题人工标注工具")
st.caption("老师直接打开链接即可标注；最后点击下载，把结果文件发回给我。")

with st.sidebar:
    st.subheader("任务设置")

    teacher_label_to_key = {v["name"]: k for k, v in TASK_MAP.items()}
    labels = list(teacher_label_to_key.keys())
    selected_teacher_label = st.selectbox(
        "选择老师",
        labels,
        index=labels.index(teacher_name),
    )
    selected_teacher_key = teacher_label_to_key[selected_teacher_label]

    if selected_teacher_key != teacher_key:
        set_query_teacher(selected_teacher_key)
        st.rerun()

    done_count = sum(1 for x in records if current_is_done(x))
    st.metric("总题数", total)
    st.metric("已完成", done_count)
    st.metric("未完成", total - done_count)
    st.progress(done_count / total if total else 0.0)

    st.divider()
    st.subheader("快速跳转")

    titles = [get_record_title(i, r) for i, r in enumerate(records)]
    if titles:
        selected_title = st.selectbox(
            "题目列表",
            titles,
            index=st.session_state.current_index,
            key="jump_selectbox",
        )
        jump_index = titles.index(selected_title)
        if jump_index != st.session_state.current_index:
            jump_to(jump_index)
            st.rerun()

    only_unfinished = st.checkbox("只看未完成题", value=False)
    if only_unfinished:
        unfinished = [i for i, x in enumerate(records) if not current_is_done(x)]
        if unfinished:
            if st.button("跳到下一道未完成题", use_container_width=True):
                current = st.session_state.current_index
                target = None
                for item_index in unfinished:
                    if item_index > current:
                        target = item_index
                        break
                if target is None:
                    target = unfinished[0]
                jump_to(target)
                st.rerun()
        else:
            st.success("当前任务已全部完成。")

    st.divider()
    export_bytes = save_download_bytes(records)
    st.download_button(
        "下载当前标注结果 JSON",
        data=export_bytes,
        file_name=make_export_name(teacher_key),
        mime="application/json",
        use_container_width=True,
    )

if total == 0:
    st.warning("当前没有可标注题目。")
    st.stop()

idx = st.session_state.current_index
record = records[idx]

st.subheader(f"{teacher_name}：第 {idx + 1} / {total} 题")
col_nav1, col_nav2, col_nav3 = st.columns([1, 1, 3])
with col_nav1:
    st.button("⬅ 上一题", on_click=move, args=(-1,), disabled=(idx == 0), use_container_width=True)
with col_nav2:
    st.button("下一题 ➡", on_click=move, args=(1,), disabled=(idx == total - 1), use_container_width=True)
with col_nav3:
    if current_is_done(record):
        st.success("本题已完成")
    else:
        st.warning("本题未完成")

left, right = st.columns([1.3, 1])

with left:
    st.markdown("### 题目信息")
    st.markdown(f"**题目ID：** `{record.get('id', '')}`")
    st.markdown(f"**题型：** {record.get('type', '')}")
    if record.get("difficulty"):
        st.markdown(f"**难度：** {record.get('difficulty', '')}")
    if record.get("grades"):
        st.markdown(f"**年级：** {'、'.join(record.get('grades', []))}")

    st.markdown("#### 题干")
    st.write(record.get("normalized_stem") or record.get("stem", ""))

    stem_images = record.get("stem_images", [])
    if stem_images:
        st.markdown("#### 题干图片")
        render_images(stem_images)

    options = record.get("options", [])
    if options:
        st.markdown("#### 选项")
        for option in options:
            option_text = option.get("text", "")
            st.write(f"{option.get('index', '')}. {option_text}")
            if option.get("images"):
                render_images(option.get("images"))

    st.markdown("#### 参考答案")
    st.write(record.get("answer", ""))

    st.markdown("#### 解析")
    st.write(record.get("normalized_analysis") or record.get("analysis", ""))

    analysis_images = record.get("analysis_images", [])
    if analysis_images:
        st.markdown("#### 解析图片")
        render_images(analysis_images)

with right:
    st.markdown("### 大模型建议")
    model_bloom = record.get("bloom_level", "")
    model_bloom_reason = record.get("bloom_reason", "")
    model_primary = record.get("core_literacy_primary", "")
    model_candidates = record.get("core_literacy_candidates", [])
    model_reason = record.get("core_literacy_reason", "")

    st.info(
        f"**Bloom：** {model_bloom or '无'}\n\n"
        f"**Bloom原因：** {model_bloom_reason or '无'}\n\n"
        f"**核心素养主标签：** {model_primary or '无'}\n\n"
        f"**核心素养候选：** {', '.join(model_candidates) if model_candidates else '无'}\n\n"
        f"**核心素养原因：** {model_reason or '无'}"
    )

    st.markdown("### 人工标注")

    current_primary = record.get("human_core_literacy_primary") or model_primary
    current_candidates = record.get("human_core_literacy_candidates") or model_candidates
    current_candidates = ensure_candidates_include_primary(current_primary, current_candidates)

    bloom_candidate = record.get("human_bloom_level") or model_bloom
    default_bloom_index = BLOOM_LEVELS.index(bloom_candidate) if bloom_candidate in BLOOM_LEVELS else 0
    default_primary_index = CORE_LITERACIES.index(current_primary) if current_primary in CORE_LITERACIES else 0

    with st.form(key=f"annotate_form_{idx}", clear_on_submit=False):
        bloom_value = st.radio(
            "Bloom 层级",
            options=BLOOM_LEVELS,
            index=default_bloom_index,
            horizontal=True,
            key=f"bloom_{idx}",
        )

        primary_value = st.selectbox(
            "核心素养主标签",
            options=CORE_LITERACIES,
            index=default_primary_index,
            key=f"primary_{idx}",
        )

        candidates_value = st.multiselect(
            "核心素养候选（最多 3 个）",
            options=CORE_LITERACIES,
            default=current_candidates,
            max_selections=3,
            key=f"candidates_{idx}",
        )

        accept_model = st.checkbox(
            "采纳大模型建议",
            value=bool(record.get("human_accept_model", False)),
            key=f"accept_{idx}",
        )

        comment = st.text_area(
            "备注",
            value=record.get("human_comment", ""),
            height=120,
            key=f"comment_{idx}",
        )

        submitted = st.form_submit_button("保存当前题", use_container_width=True)

    if submitted:
        candidates_value = ensure_candidates_include_primary(primary_value, candidates_value)
        st.session_state.records[idx] = build_annotated_record(
            record=st.session_state.records[idx],
            annotator_name=teacher_name,
            bloom_value=bloom_value,
            primary_value=primary_value,
            candidates_value=candidates_value,
            accept_model=accept_model,
            comment=comment,
        )
        st.success("已保存当前题。")

    st.divider()
    st.markdown("### 当前人工结果")
    preview = st.session_state.records[idx]
    st.write({
        "human_bloom_level": preview.get("human_bloom_level", ""),
        "human_core_literacy_primary": preview.get("human_core_literacy_primary", ""),
        "human_core_literacy_candidates": preview.get("human_core_literacy_candidates", []),
        "human_accept_model": preview.get("human_accept_model", False),
        "human_comment": preview.get("human_comment", ""),
        "human_status": preview.get("human_status", "未完成"),
        "human_updated_at": preview.get("human_updated_at", ""),
    })
