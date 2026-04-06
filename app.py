from __future__ import annotations

import csv
import html
import io
import json
from collections import Counter
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
IMAGES_DIR = BASE_DIR / "images"
COMPONENT_DIR = BASE_DIR / "components" / "local_storage"

BLOOM_OPTIONS = ["记忆", "理解", "应用", "分析", "评价", "创造"]
COMMON_CORE_ORDER = [
    "抽象能力",
    "运算能力",
    "推理能力",
    "模型观念",
    "空间观念",
    "数据观念",
    "应用意识",
    "创新意识",
]
STATUS_LABELS = {
    "empty": ("⚪", "未开始"),
    "partial": ("🟡", "待完成"),
    "done": ("🟢", "已完成"),
}
BLOOM_HINTS = {
    "记忆": "识别、回忆定义、公式、结论。",
    "理解": "解释概念、辨别关系、说明原理。",
    "应用": "把已知知识用于具体求解或计算。",
    "分析": "拆解条件、比较结构、建立关系。",
    "评价": "判断方法优劣、检验结论、给出依据。",
    "创造": "构造新方法、开放设计、多策略生成。",
}
CORE_HINTS = {
    "抽象能力": "从具体情境中提取数量关系、结构和一般规律。",
    "运算能力": "聚焦化简、计算、变形与符号运算。",
    "推理能力": "依靠条件分析、逻辑推导和论证得到结论。",
    "模型观念": "把实际或几何问题转成函数、方程、不等式等模型求解。",
    "空间观念": "关注图形位置关系、形状特征与空间想象。",
    "数据观念": "围绕数据读取、统计分析、表示与解释。",
    "应用意识": "强调数学与真实情境的联系与迁移应用。",
    "创新意识": "鼓励多路径解决、策略创造与问题重构。",
}

st.set_page_config(page_title="题目标注工具", layout="wide")

LOCAL_COMPONENT_HTML = r"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <script src="https://unpkg.com/streamlit-component-lib@2.0.0/dist/index.js"></script>
  </head>
  <body>
    <script>
      const LS = {
        get(key, fallbackValue="") {
          try {
            const value = window.localStorage.getItem(key);
            return value === null ? fallbackValue : value;
          } catch (e) {
            return fallbackValue;
          }
        },
        set(key, value) {
          try {
            window.localStorage.setItem(key, value ?? "");
          } catch (e) {}
        }
      };

      function sendValue() {
        const args = window.Streamlit?.args || {};
        const storageKey = args.storage_key || "";
        const defaultValue = args.default ?? "";
        const value = args.value;

        if (storageKey) {
          if (value !== undefined && value !== null) {
            LS.set(storageKey, value);
          }
          const current = LS.get(storageKey, defaultValue);
          window.Streamlit.setComponentValue(current);
        } else {
          window.Streamlit.setComponentValue(defaultValue);
        }
      }

      function onRender(event) {
        window.Streamlit.setFrameHeight(0);
        sendValue();
      }

      window.addEventListener("storage", sendValue);
      window.Streamlit.events.addEventListener(window.Streamlit.RENDER_EVENT, onRender);
      window.Streamlit.setComponentReady();
      window.Streamlit.setFrameHeight(0);
    </script>
  </body>
</html>
"""


def ensure_local_component() -> Path:
    component_dir = BASE_DIR / "components" / "local_storage"
    component_dir.mkdir(parents=True, exist_ok=True)
    index_file = component_dir / "index.html"
    if (not index_file.exists()) or ("streamlit-component-lib" not in index_file.read_text(encoding="utf-8", errors="ignore")):
        index_file.write_text(LOCAL_COMPONENT_HTML, encoding="utf-8")
    return component_dir


COMPONENT_DIR = ensure_local_component()

LOCAL_STORAGE = components.declare_component(
    "local_storage_bridge",
    path=str(COMPONENT_DIR),
)


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def now_display() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def storage_value(storage_key: str, value: str | None = None, widget_key: str | None = None):
    return LOCAL_STORAGE(
        storage_key=storage_key,
        value=value,
        default="",
        key=widget_key or f"storage::{storage_key}",
    )


def discover_datasets() -> list[Path]:
    if not DATA_DIR.exists():
        return []
    return sorted(DATA_DIR.glob("*.json"))


def load_questions(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        questions = data
    elif isinstance(data, dict):
        for key in ("questions", "data", "items", "records"):
            value = data.get(key)
            if isinstance(value, list):
                questions = value
                break
        else:
            questions = [data]
    else:
        raise ValueError(f"无法识别的数据结构: {path.name}")

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(questions, start=1):
        if not isinstance(item, dict):
            continue
        q = dict(item)
        q.setdefault("id", f"q_{idx:04d}")
        q.setdefault("type", "")
        q.setdefault("score", "")
        q.setdefault("answer", "")
        q.setdefault("stem_images", [])
        q.setdefault("analysis_images", [])
        q.setdefault("options", [])
        q.setdefault("knowledges", [])
        q.setdefault("abilities", [])
        q.setdefault("difficulty", "")
        q.setdefault("grades", [])
        q.setdefault("bnu_knowledges", [])
        q.setdefault("xkb_knowledges", [])
        q.setdefault("normalized_stem", "")
        q.setdefault("normalized_analysis", "")
        q.setdefault("bloom_level", "")
        q.setdefault("bloom_reason", "")
        q.setdefault("core_literacy_primary", "")
        q.setdefault("core_literacy_candidates", [])
        q.setdefault("core_literacy_reason", "")
        q.setdefault("model_name", "")
        normalized.append(q)
    return normalized


def collect_core_options(questions: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    for q in questions:
        for value in q.get("core_literacy_candidates", []):
            if value and value not in found:
                found.append(value)
        primary = q.get("core_literacy_primary")
        if primary and primary not in found:
            found.append(primary)

    ordered = [item for item in COMMON_CORE_ORDER if item in found]
    tail = sorted([item for item in found if item not in ordered])
    options = ordered + tail
    return options or COMMON_CORE_ORDER


def make_empty_progress(dataset_name: str, questions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "version": 1,
        "dataset": dataset_name,
        "annotator_name": "",
        "current_index": 0,
        "last_autosave_at": "",
        "answers": {
            str(q["id"]): {
                "bloom_label": None,
                "core_literacy_label": None,
                "note": "",
                "status": "empty",
                "updated_at": "",
                "confirmed_at": "",
            }
            for q in questions
        },
    }


def coerce_progress(
    progress: dict[str, Any] | None,
    dataset_name: str,
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    base = make_empty_progress(dataset_name, questions)
    if not isinstance(progress, dict):
        return base
    merged = deepcopy(base)
    merged["annotator_name"] = progress.get("annotator_name", "") or ""
    merged["current_index"] = int(progress.get("current_index", 0) or 0)
    merged["last_autosave_at"] = progress.get("last_autosave_at", "") or ""

    incoming_answers = progress.get("answers", {})
    if isinstance(incoming_answers, dict):
        for q in questions:
            qid = str(q["id"])
            incoming = incoming_answers.get(qid, {})
            if not isinstance(incoming, dict):
                continue
            bloom_label = incoming.get("bloom_label") or None
            core_label = incoming.get("core_literacy_label") or None
            note = incoming.get("note", "") or ""
            status = compute_status(bloom_label, core_label)
            merged["answers"][qid].update(
                {
                    "bloom_label": bloom_label if bloom_label in BLOOM_OPTIONS else None,
                    "core_literacy_label": core_label,
                    "note": note,
                    "status": status,
                    "updated_at": incoming.get("updated_at", "") or "",
                    "confirmed_at": incoming.get("confirmed_at", "") or "",
                }
            )
    merged["current_index"] = max(0, min(merged["current_index"], len(questions) - 1))
    return merged


def compute_status(bloom: str | None, core: str | None) -> str:
    if bloom and core:
        return "done"
    if bloom or core:
        return "partial"
    return "empty"


def status_text(status: str) -> str:
    icon, label = STATUS_LABELS.get(status, STATUS_LABELS["empty"])
    return f"{icon} {label}"


def progress_counts(progress: dict[str, Any]) -> tuple[int, int, int]:
    values = list(progress.get("answers", {}).values())
    total = len(values)
    completed = sum(1 for item in values if item.get("status") == "done")
    partial = sum(1 for item in values if item.get("status") == "partial")
    return total, completed, partial


def next_incomplete_index(
    progress: dict[str, Any],
    questions: list[dict[str, Any]],
    start_index: int,
) -> int | None:
    total = len(questions)
    for offset in range(1, total + 1):
        idx = (start_index + offset) % total
        qid = str(questions[idx]["id"])
        if progress["answers"][qid]["status"] != "done":
            return idx
    return None


def sync_widget_value(key: str, value: Any) -> None:
    if st.session_state.get(key) != value:
        st.session_state[key] = value


def load_progress_from_browser(
    dataset_name: str,
    questions: list[dict[str, Any]],
    storage_key: str,
) -> dict[str, Any]:
    state_key = f"progress::{dataset_name}"
    init_key = f"progress_initialized::{dataset_name}"

    if not st.session_state.get(init_key, False):
        raw = storage_value(storage_key, None, widget_key=f"storage_read::{storage_key}")
        progress: dict[str, Any] | None = None
        if raw:
            try:
                progress = json.loads(raw)
            except json.JSONDecodeError:
                progress = None
        st.session_state[state_key] = coerce_progress(progress, dataset_name, questions)
        st.session_state[init_key] = True
    return st.session_state[state_key]


def persist_progress(dataset_name: str, progress: dict[str, Any], storage_key: str) -> None:
    state_key = f"progress::{dataset_name}"
    st.session_state[state_key] = progress
    serialized = json.dumps(progress, ensure_ascii=False)
    storage_value(storage_key, serialized, widget_key=f"storage_write::{storage_key}")


def pretty_badges(items: list[str], empty_text: str = "—") -> str:
    values = [str(item) for item in items if str(item).strip()]
    if not values:
        return f"<span class='muted'>{html.escape(empty_text)}</span>"
    return " ".join(
        f"<span class='tag'>{html.escape(value)}</span>" for value in values
    )


def metric_badges(question: dict[str, Any]) -> str:
    basics = [
        ("题号", question.get("id", "")),
        ("题型", question.get("type", "")),
        ("分值", question.get("score", "")),
        ("难度", question.get("difficulty", "")),
    ]
    html_parts = ["<div class='meta-grid'>"]
    for label, value in basics:
        html_parts.append(
            f"<div class='meta-item'><div class='meta-label'>{html.escape(label)}</div><div class='meta-value'>{html.escape(str(value) if value not in (None, '') else '—')}</div></div>"
        )
    html_parts.append("</div>")
    return "".join(html_parts)


def as_html_text(text: Any) -> str:
    value = "" if text is None else str(text)
    escaped = html.escape(value)
    return escaped.replace("\n", "<br>") if escaped else "<span class='muted'>—</span>"


def estimate_height(text: Any, minimum: int = 100, maximum: int = 900) -> int:
    value = "" if text is None else str(text)
    line_count = value.count("\n") + 1
    length = len(value)
    height = 70 + line_count * 24 + max(0, length // 38) * 8
    return max(minimum, min(maximum, height))


def render_math_block(title: str, text: Any, height: int | None = None) -> None:
    content = as_html_text(text)
    frame_height = height or estimate_height(text)
    html_block = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.css">
        <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.js"></script>
        <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/contrib/auto-render.min.js"></script>
        <style>
          body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: #111827;
            background: transparent;
          }}
          .math-card {{
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            padding: 14px 16px;
          }}
          .math-title {{
            font-size: 14px;
            color: #374151;
            font-weight: 700;
            margin-bottom: 10px;
          }}
          .math-content {{
            font-size: 16px;
            line-height: 1.8;
            word-break: break-word;
          }}
          .muted {{
            color: #6b7280;
          }}
        </style>
      </head>
      <body>
        <div class="math-card">
          <div class="math-title">{html.escape(title)}</div>
          <div class="math-content" id="math-content">{content}</div>
        </div>
        <script>
          document.addEventListener("DOMContentLoaded", function() {{
            if (window.renderMathInElement) {{
              renderMathInElement(document.getElementById("math-content"), {{
                delimiters: [
                  {{left: "$$", right: "$$", display: true}},
                  {{left: "$", right: "$", display: false}},
                  {{left: "\\(", right: "\\)", display: false}},
                  {{left: "\\[", right: "\\]", display: true}}
                ],
                throwOnError: false
              }});
            }}
          }});
        </script>
      </body>
    </html>
    """
    components.html(html_block, height=frame_height, scrolling=False)


def resolve_image(image_path: str) -> Path:
    candidate = (BASE_DIR / image_path).resolve()
    if candidate.exists():
        return candidate
    candidate = (IMAGES_DIR / Path(image_path).name).resolve()
    return candidate


def show_images(title: str, paths: list[str]) -> None:
    valid_paths = []
    captions = []
    for relative in paths or []:
        absolute = resolve_image(relative)
        if absolute.exists():
            valid_paths.append(str(absolute))
            captions.append(Path(relative).name)
    if valid_paths:
        st.markdown(f"**{title}**")
        st.image(valid_paths, caption=captions, use_container_width=True)


def format_jump_option(index: int, questions: list[dict[str, Any]], progress: dict[str, Any]) -> str:
    q = questions[index]
    qid = str(q.get("id", index + 1))
    status = progress["answers"][qid]["status"]
    return f"{index + 1:>3} · {qid} · {status_text(status)}"


def export_rows(
    dataset_name: str,
    questions: list[dict[str, Any]],
    progress: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, q in enumerate(questions, start=1):
        qid = str(q["id"])
        ann = progress["answers"][qid]
        rows.append(
            {
                "dataset": dataset_name,
                "index": idx,
                "id": qid,
                "type": q.get("type", ""),
                "score": q.get("score", ""),
                "annotated_bloom_level": ann.get("bloom_label") or "",
                "annotated_core_literacy": ann.get("core_literacy_label") or "",
                "annotator_note": ann.get("note") or "",
                "status": ann.get("status") or "",
                "updated_at": ann.get("updated_at") or "",
                "confirmed_at": ann.get("confirmed_at") or "",
                "model_bloom_level": q.get("bloom_level", ""),
                "model_bloom_reason": q.get("bloom_reason", ""),
                "model_core_literacy": q.get("core_literacy_primary", ""),
                "model_core_literacy_reason": q.get("core_literacy_reason", ""),
            }
        )
    return rows


def export_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def make_backup_payload(
    dataset_name: str,
    questions: list[dict[str, Any]],
    progress: dict[str, Any],
) -> dict[str, Any]:
    return {
        "tool": "annotation_tool",
        "exported_at": now_iso(),
        "dataset": dataset_name,
        "question_count": len(questions),
        "progress": progress,
    }


def apply_global_styles() -> None:
    st.markdown(
        """
        <style>
          .block-container {
            padding-top: 1.2rem;
            padding-bottom: 1.2rem;
          }
          .page-title {
            font-size: 1.8rem;
            font-weight: 800;
            margin-bottom: 0.2rem;
          }
          .page-subtitle {
            color: #6b7280;
            margin-bottom: 1rem;
          }
          .meta-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
            margin-bottom: 12px;
          }
          .meta-item {
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            padding: 12px 14px;
            background: #fff;
          }
          .meta-label {
            font-size: 12px;
            color: #6b7280;
            margin-bottom: 4px;
          }
          .meta-value {
            font-size: 16px;
            font-weight: 700;
            color: #111827;
          }
          .tag {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            background: #eef2ff;
            color: #3730a3;
            border: 1px solid #c7d2fe;
            font-size: 12px;
            margin: 0 6px 6px 0;
          }
          .muted {
            color: #6b7280;
          }
          .hint-box {
            border: 1px solid #e5e7eb;
            background: #fafafa;
            border-radius: 14px;
            padding: 12px 14px;
          }
          .section-title {
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 0.35rem;
          }
          .small-help {
            color: #6b7280;
            font-size: 0.9rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    apply_global_styles()

    st.markdown('<div class="page-title">题目标注工具</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-subtitle">支持 Bloom 层级与核心素养标注，浏览器本地自动保存，全部完成后可直接导出。</div>',
        unsafe_allow_html=True,
    )

    datasets = discover_datasets()
    if not datasets:
        st.error("未找到 data 目录下的 JSON 文件。请确认目录结构为 data/*.json。")
        st.stop()

    dataset_names = [path.name for path in datasets]
    query_file = st.query_params.get("file", dataset_names[0])
    if isinstance(query_file, list):
        query_file = query_file[0] if query_file else dataset_names[0]
    default_dataset = query_file if query_file in dataset_names else dataset_names[0]

    top_left, top_mid, top_right = st.columns([1.2, 1.2, 1.6])
    with top_left:
        selected_dataset = st.selectbox(
            "数据集",
            dataset_names,
            index=dataset_names.index(default_dataset),
            help="也可通过 URL 参数 ?file=teacher_1.json 指定数据集。",
        )
    st.query_params["file"] = selected_dataset

    data_path = next(path for path in datasets if path.name == selected_dataset)
    questions = load_questions(data_path)
    if not questions:
        st.error(f"{selected_dataset} 中没有可用题目。")
        st.stop()

    annotator_param = st.query_params.get("annotator", "")
    if isinstance(annotator_param, list):
        annotator_param = annotator_param[0] if annotator_param else ""
    storage_key = f"annotation_tool::{selected_dataset}"
    if annotator_param:
        storage_key += f"::{annotator_param}"

    progress = load_progress_from_browser(selected_dataset, questions, storage_key)
    core_options = collect_core_options(questions)

    total, completed, partial = progress_counts(progress)
    unfinished = total - completed

    with top_mid:
        st.metric("完成进度", f"{completed}/{total}", delta=f"剩余 {unfinished}")
    with top_right:
        saved_at = progress.get("last_autosave_at") or "尚未自动保存"
        st.info(f"当前数据集：**{selected_dataset}**\n\n自动保存：**{saved_at}**")

    with st.sidebar:
        st.header("辅助功能")
        annotator_name = st.text_input(
            "标注者姓名/代号（可选）",
            value=progress.get("annotator_name", "") or annotator_param,
            help="仅用于导出文件名和结果记录，不影响标注内容。",
        )
        if annotator_name != progress.get("annotator_name", ""):
            progress["annotator_name"] = annotator_name
            progress["last_autosave_at"] = now_display()
            persist_progress(selected_dataset, progress, storage_key)

        jump_key = f"jump::{selected_dataset}"
        sync_widget_value(jump_key, progress.get("current_index", 0))
        jump_index = st.selectbox(
            "跳转到题目",
            list(range(len(questions))),
            format_func=lambda i: format_jump_option(i, questions, progress),
            key=jump_key,
        )
        if jump_index != progress.get("current_index", 0):
            progress["current_index"] = int(jump_index)
            progress["last_autosave_at"] = now_display()
            persist_progress(selected_dataset, progress, storage_key)
            st.rerun()

        if st.button("跳到下一道未完成", use_container_width=True):
            target = next_incomplete_index(progress, questions, progress["current_index"])
            if target is None:
                st.toast("当前数据集已经全部完成。", icon="✅")
            else:
                progress["current_index"] = target
                progress["last_autosave_at"] = now_display()
                persist_progress(selected_dataset, progress, storage_key)
                st.rerun()

        st.divider()
        st.caption("Bloom 参考")
        for option in BLOOM_OPTIONS:
            st.markdown(f"**{option}**：{BLOOM_HINTS[option]}")

        st.divider()
        st.caption("本地保存说明")
        st.write("进度保存在当前浏览器的本地存储中，刷新页面不会丢失。更换设备前建议先下载备份。")

        backup_payload = make_backup_payload(selected_dataset, questions, progress)
        backup_name = f"backup_{selected_dataset.replace('.json', '')}"
        if annotator_name:
            backup_name += f"_{annotator_name}"
        backup_name += ".json"
        st.download_button(
            "下载当前进度备份",
            data=json.dumps(backup_payload, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=backup_name,
            mime="application/json",
            use_container_width=True,
        )

        uploaded_backup = st.file_uploader("导入进度备份", type=["json"])
        import_guard_key = f"import_guard::{selected_dataset}"
        if uploaded_backup is not None:
            upload_signature = f"{uploaded_backup.name}:{uploaded_backup.size}"
            if st.session_state.get(import_guard_key) != upload_signature:
                try:
                    imported = json.load(uploaded_backup)
                    imported_progress = imported.get("progress") if isinstance(imported, dict) else None
                    progress = coerce_progress(imported_progress, selected_dataset, questions)
                    progress["last_autosave_at"] = now_display()
                    persist_progress(selected_dataset, progress, storage_key)
                    st.session_state[import_guard_key] = upload_signature
                    st.success("进度备份已导入。")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"导入失败：{exc}")
        else:
            st.session_state.pop(import_guard_key, None)

        with st.expander("重置当前数据集进度", expanded=False):
            st.warning("此操作会清空当前浏览器中该数据集的本地保存记录。")
            if st.button("确认清空", type="secondary", use_container_width=True):
                progress = make_empty_progress(selected_dataset, questions)
                progress["annotator_name"] = annotator_name
                progress["last_autosave_at"] = now_display()
                persist_progress(selected_dataset, progress, storage_key)
                st.success("已清空当前数据集进度。")
                st.rerun()

        st.divider()
        bloom_counter = Counter(
            item.get("bloom_label") for item in progress["answers"].values() if item.get("bloom_label")
        )
        core_counter = Counter(
            item.get("core_literacy_label")
            for item in progress["answers"].values()
            if item.get("core_literacy_label")
        )
        st.caption("已选标签分布")
        if bloom_counter:
            st.write("Bloom：" + " / ".join(f"{k}({v})" for k, v in bloom_counter.items()))
        else:
            st.write("Bloom：暂无")
        if core_counter:
            st.write("核心素养：" + " / ".join(f"{k}({v})" for k, v in core_counter.items()))
        else:
            st.write("核心素养：暂无")

    current_index = max(0, min(progress.get("current_index", 0), len(questions) - 1))
    question = questions[current_index]
    qid = str(question["id"])
    ann = progress["answers"][qid]

    widget_bloom_key = f"widget_bloom::{selected_dataset}::{qid}"
    widget_core_key = f"widget_core::{selected_dataset}::{qid}"
    widget_note_key = f"widget_note::{selected_dataset}::{qid}"
    sync_widget_value(widget_bloom_key, ann.get("bloom_label"))
    sync_widget_value(widget_core_key, ann.get("core_literacy_label"))
    sync_widget_value(widget_note_key, ann.get("note", ""))

    left, right = st.columns([1.55, 1.0], gap="large")

    with left:
        st.subheader(f"题目区 · 第 {current_index + 1} / {len(questions)} 题")
        with st.container(height=820, border=True):
            st.markdown(metric_badges(question), unsafe_allow_html=True)
            st.markdown("**年级**")
            st.markdown(pretty_badges(question.get("grades", [])), unsafe_allow_html=True)
            st.markdown("**知识点**")
            st.markdown(pretty_badges(question.get("knowledges", [])), unsafe_allow_html=True)
            st.markdown("**北师大知识点**")
            st.markdown(pretty_badges(question.get("bnu_knowledges", [])), unsafe_allow_html=True)
            st.markdown("**课标知识点**")
            st.markdown(pretty_badges(question.get("xkb_knowledges", [])), unsafe_allow_html=True)
            st.markdown("**能力要求**")
            st.markdown(pretty_badges(question.get("abilities", [])), unsafe_allow_html=True)

            render_math_block("题干", question.get("normalized_stem", ""), height=estimate_height(question.get("normalized_stem", ""), minimum=180, maximum=780))
            show_images("题干图片", question.get("stem_images", []))
            render_math_block("答案", question.get("answer", ""), height=estimate_height(question.get("answer", ""), minimum=90, maximum=260))
            render_math_block("解析", question.get("normalized_analysis", ""), height=estimate_height(question.get("normalized_analysis", ""), minimum=260, maximum=1200))
            show_images("解析图片", question.get("analysis_images", []))

    with right:
        st.subheader("标注区")
        status = ann.get("status", "empty")
        if status == "done":
            st.success(f"当前题状态：{status_text(status)}")
        elif status == "partial":
            st.warning(f"当前题状态：{status_text(status)}")
        else:
            st.info(f"当前题状态：{status_text(status)}")

        model_name = question.get("model_name", "") or "模型"
        with st.expander("大模型建议参考", expanded=True):
            st.markdown(
                f"<div class='hint-box'><div class='section-title'>Bloom 建议</div><div><b>{html.escape(question.get('bloom_level') or '—')}</b></div><div class='small-help'>{html.escape(question.get('bloom_reason') or '未提供')}</div></div>",
                unsafe_allow_html=True,
            )
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("采用 Bloom 建议", key=f"use_bloom::{qid}", use_container_width=True):
                    suggestion = question.get("bloom_level")
                    if suggestion in BLOOM_OPTIONS:
                        st.session_state[widget_bloom_key] = suggestion
                        st.rerun()
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            st.markdown(
                f"<div class='hint-box'><div class='section-title'>核心素养建议</div><div><b>{html.escape(question.get('core_literacy_primary') or '—')}</b></div><div class='small-help'>候选：{html.escape(' / '.join(question.get('core_literacy_candidates', [])) or '未提供')}</div><div class='small-help' style='margin-top:6px;'>{html.escape(question.get('core_literacy_reason') or '未提供')}</div><div class='small-help' style='margin-top:6px;'>来源模型：{html.escape(model_name)}</div></div>",
                unsafe_allow_html=True,
            )
            with col_b:
                if st.button("采用核心素养建议", key=f"use_core::{qid}", use_container_width=True):
                    suggestion = question.get("core_literacy_primary")
                    if suggestion:
                        st.session_state[widget_core_key] = suggestion
                        st.rerun()

        bloom_choice = st.radio(
            "1. Bloom 层级标注",
            BLOOM_OPTIONS,
            index=None,
            horizontal=True,
            key=widget_bloom_key,
            captions=[BLOOM_HINTS[item] for item in BLOOM_OPTIONS],
        )

        core_choice = st.radio(
            "2. 核心素养标注",
            core_options,
            index=None,
            key=widget_core_key,
        )

        note_value = st.text_area(
            "3. 标注备注（可选）",
            height=100,
            placeholder="可记录边界情况、争议点或复核意见。",
            key=widget_note_key,
        )

        if bloom_choice and question.get("bloom_level") and bloom_choice != question.get("bloom_level"):
            st.caption(f"你当前的 Bloom 选择与模型建议不同：模型建议为 {question.get('bloom_level')}。")
        if core_choice and question.get("core_literacy_primary") and core_choice != question.get("core_literacy_primary"):
            st.caption(f"你当前的核心素养选择与模型建议不同：模型建议为 {question.get('core_literacy_primary')}。")

        new_status = compute_status(bloom_choice, core_choice)
        changed = any(
            [
                ann.get("bloom_label") != bloom_choice,
                ann.get("core_literacy_label") != core_choice,
                (ann.get("note") or "") != (note_value or ""),
                ann.get("status") != new_status,
            ]
        )
        if changed:
            ann["bloom_label"] = bloom_choice
            ann["core_literacy_label"] = core_choice
            ann["note"] = note_value or ""
            ann["status"] = new_status
            ann["updated_at"] = now_iso()
            progress["current_index"] = current_index
            progress["last_autosave_at"] = now_display()
            persist_progress(selected_dataset, progress, storage_key)

        st.markdown("---")
        col_prev, col_next, col_save = st.columns(3)
        with col_prev:
            prev_clicked = st.button("上一题", use_container_width=True, disabled=current_index == 0)
        with col_next:
            next_clicked = st.button("下一题", use_container_width=True, disabled=current_index >= len(questions) - 1)
        with col_save:
            save_next_clicked = st.button(
                "保存并下一题",
                type="primary",
                use_container_width=True,
            )

        if prev_clicked:
            progress["current_index"] = max(0, current_index - 1)
            progress["last_autosave_at"] = now_display()
            persist_progress(selected_dataset, progress, storage_key)
            st.toast("已切换到上一题。", icon="⬅️")
            st.rerun()

        if next_clicked:
            progress["current_index"] = min(len(questions) - 1, current_index + 1)
            progress["last_autosave_at"] = now_display()
            persist_progress(selected_dataset, progress, storage_key)
            if new_status == "done":
                st.toast("已自动保存并切换到下一题。", icon="➡️")
            else:
                st.toast("已保存当前草稿并切换到下一题。", icon="➡️")
            st.rerun()

        if save_next_clicked:
            if not bloom_choice or not core_choice:
                st.toast("请先完成 Bloom 层级和核心素养标注后再保存。", icon="⚠️")
            else:
                ann["status"] = "done"
                ann["confirmed_at"] = now_iso()
                ann["updated_at"] = now_iso()
                progress["last_autosave_at"] = now_display()
                progress["current_index"] = min(len(questions) - 1, current_index + 1)
                persist_progress(selected_dataset, progress, storage_key)
                if current_index == len(questions) - 1:
                    st.toast("当前题已保存。你已到最后一题。", icon="✅")
                else:
                    st.toast("保存成功，已进入下一题。", icon="✅")
                st.rerun()

        st.markdown("---")
        completed_now = progress_counts(progress)[1]
        st.progress(completed_now / len(questions))
        st.caption(f"已完成 {completed_now} / {len(questions)} 题；待完成 {len(questions) - completed_now} 题。")

        rows = export_rows(selected_dataset, questions, progress)
        export_disabled = completed_now != len(questions)
        export_name_prefix = selected_dataset.replace(".json", "")
        if annotator_name:
            export_name_prefix += f"_{annotator_name}"

        csv_bytes = export_csv_bytes(rows)
        json_bytes = json.dumps(
            {
                "dataset": selected_dataset,
                "annotator_name": annotator_name,
                "exported_at": now_iso(),
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

        st.download_button(
            "下载最终 CSV",
            data=csv_bytes,
            file_name=f"annotation_result_{export_name_prefix}.csv",
            mime="text/csv",
            disabled=export_disabled,
            use_container_width=True,
            help="全部题目标注完成后可下载。",
        )
        st.download_button(
            "下载最终 JSON",
            data=json_bytes,
            file_name=f"annotation_result_{export_name_prefix}.json",
            mime="application/json",
            disabled=export_disabled,
            use_container_width=True,
            help="全部题目标注完成后可下载。",
        )
        if export_disabled:
            st.caption("全部题目标注完成后，下载按钮会自动可用。")
        else:
            st.success("全部题目已完成，可以导出结果。")

    st.caption(
        "链接分发建议：部署后直接分享形如 ?file=teacher_1.json、?file=teacher_2.json、?file=teacher_3.json 的三个链接即可；每位标注者的进度默认保存在其浏览器本地。"
    )


if __name__ == "__main__":
    main()
