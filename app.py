import json
import re
from pathlib import Path
from datetime import datetime
from copy import deepcopy

import streamlit as st

# =========================
# 页面基础配置
# =========================
st.set_page_config(page_title="数字题人工标注工具 Pro", layout="wide", initial_sidebar_state="expanded")

BLOOM_LEVELS = ["记忆", "理解", "应用", "分析", "评价", "创造"]
CORE_LITERACIES = [
    "抽象能力", "运算能力", "几何直观", "空间观念", "推理能力",
    "数据观念", "模型观念", "应用意识", "创新意识",
]
TASK_MAP = {
    "teacher1": {"label": "标注员 A", "file": "data/teacher1.json"},
    "teacher2": {"label": "标注员 B", "file": "data/teacher2.json"},
    "teacher3": {"label": "标注员 C", "file": "data/teacher3.json"},
}

BASE_DIR = Path(__file__).parent
AUTOSAVE_DIR = BASE_DIR / ".autosave"

# 注入自定义 CSS
st.markdown("""
<style>
    .main .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    /* 强制限制图片最大高度，防止霸屏 */
    [data-testid="stImage"] img {
        max-height: 400px !important;
        object-fit: contain;
    }
    .stAlert { padding: 0.5rem; margin-bottom: 0.5rem; }
    .small-muted { color: #666; font-size: 0.85rem; line-height: 1.4; }
</style>
""", unsafe_allow_html=True)

# =========================
# 核心工具函数
# =========================
def sanitize_math_text(text: str) -> str:
    if not text: return ""
    s = str(text)
    # 基础 LaTeX 转换
    s = s.replace("\\(", "$").replace("\\)", "$").replace("\\[", "$$").replace("\\]", "$$")
    s = s.replace("⩽", "\\leqslant").replace("⩾", "\\geqslant")
    s = s.replace("\\vartriangle", "\\triangle").replace("vartriangle", "\\triangle")
    # 清理非标准符号
    s = s.replace("{^\\circ}", "^{\\circ}").replace("{\\circ}", "^{\\circ}")
    s = re.sub(r'(\d+)\s*\{\s*\\\\circ\s*\}', r'\1^{\\circ}', s)
    s = re.sub(r'(?<!\\)sqrt\s*([0-9a-zA-Z]+)', r'\\sqrt{\1}', s)
    # 自动给孤立的度数补全 $ 符号
    s = re.sub(r'(?<!\$)(\d+\s*\^\\circ)(?!\$)', r'$\1$', s)
    return s.strip()

def render_rich_text(text: str, label: str = ""):
    if not text: return
    clean = sanitize_math_text(text)
    try:
        st.markdown(clean.replace("\n", "  \n"))
    except:
        st.code(text)

def load_data(path: Path):
    if not path.exists(): return []
    content = path.read_text(encoding="utf-8")
    return json.loads(content) if content else []

def try_write_autosave(teacher_key, records):
    AUTOSAVE_DIR.mkdir(exist_ok=True)
    path = AUTOSAVE_DIR / f"{teacher_key}_autosave.json"
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

# =========================
# 状态与动作逻辑
# =========================
def init_session():
    t_key = st.query_params.get("teacher", "teacher1")
    if t_key not in TASK_MAP: t_key = "teacher1"
    
    rec_key = f"rec_{t_key}"
    if rec_key not in st.session_state:
        # 优先读自动保存
        auto_path = AUTOSAVE_DIR / f"{t_key}_autosave.json"
        orig_path = BASE_DIR / TASK_MAP[t_key]["file"]
        st.session_state[rec_key] = load_data(auto_path) if auto_path.exists() else load_data(orig_path)
    
    if "idx" not in st.session_state: st.session_state.idx = 0
    st.session_state.t_key = t_key

def sync_widgets():
    """将数据从 Record 刷新到 Widget 状态中"""
    if not st.session_state.get("needs_sync", True): return
    
    idx = st.session_state.idx
    records = st.session_state[f"rec_{st.session_state.t_key}"]
    if not records: return
    item = records[idx]
    
    st.session_state.ebloom = item.get("human_bloom_level") or item.get("bloom_level") or BLOOM_LEVELS[0]
    st.session_state.eprimary = item.get("human_core_literacy_primary") or item.get("core_literacy_primary") or CORE_LITERACIES[0]
    st.session_state.ecand = item.get("human_core_literacy_candidates") or item.get("core_literacy_candidates") or []
    st.session_state.eaccept = bool(item.get("human_accept_model", False))
    st.session_state.ecomm_b = item.get("human_comment_bloom", "")
    st.session_state.ecomm_c = item.get("human_comment_core", "")
    st.session_state.needs_sync = False

def save_current():
    idx = st.session_state.idx
    t_key = st.session_state.t_key
    records = st.session_state[f"rec_{t_key}"]
    
    records[idx].update({
        "human_bloom_level": st.session_state.ebloom,
        "human_core_literacy_primary": st.session_state.eprimary,
        "human_core_literacy_candidates": st.session_state.ecand,
        "human_accept_model": st.session_state.eaccept,
        "human_comment_bloom": st.session_state.ecomm_b,
        "human_comment_core": st.session_state.ecomm_c,
        "human_updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    try_write_autosave(t_key, records)

def check_diff():
    """判断当前编辑的内容是否和已存内容不一致"""
    idx = st.session_state.idx
    item = st.session_state[f"rec_{st.session_state.t_key}"][idx]
    return any([
        st.session_state.ebloom != (item.get("human_bloom_level") or item.get("bloom_level") or BLOOM_LEVELS[0]),
        st.session_state.eprimary != (item.get("human_core_literacy_primary") or item.get("core_literacy_primary") or CORE_LITERACIES[0]),
        st.session_state.ecomm_b != item.get("human_comment_bloom", ""),
        st.session_state.ecomm_c != item.get("human_comment_core", ""),
    ])

# =========================
# UI 渲染
# =========================
init_session()
records = st.session_state[f"rec_{st.session_state.t_key}"]
if not records:
    st.error("未加载到有效数据")
    st.stop()

sync_widgets()
curr_item = records[st.session_state.idx]

# 侧边栏控制
with st.sidebar:
    st.header("⚙️ 配置与统计")
    done_count = sum(1 for r in records if r.get("human_bloom_level"))
    st.metric("进度", f"{done_count} / {len(records)}", f"{int(done_count/len(records)*100)}%")
    
    panel_h = st.slider("面板高度", 500, 1000, 780)
    img_w = st.slider("图片宽度", 200, 600, 350)
    
    st.divider()
    
    # 题目选择
    titles = [f"{'✅' if r.get('human_bloom_level') else '⬜'} {i+1}. {r.get('id','...')[:10]}" for i,r in enumerate(records)]
    new_idx = st.selectbox("跳转题目", range(len(titles)), format_func=lambda x: titles[x], index=st.session_state.idx)
    if new_idx != st.session_state.idx:
        st.session_state.idx = new_idx
        st.session_state.needs_sync = True
        st.rerun()

    st.download_button("📤 导出最终 JSON", json.dumps(records, ensure_ascii=False, indent=2), f"result_{st.session_state.t_key}.json", "application/json", use_container_width=True)

# 顶部导航
c1, c2, c3, c4 = st.columns([1,1,2,1])
with c1:
    if st.button("⬅️ 上一题", use_container_width=True) and st.session_state.idx > 0:
        st.session_state.idx -= 1
        st.session_state.needs_sync = True
        st.rerun()
with c2:
    if st.button("下一题 ➡️", use_container_width=True) and st.session_state.idx < len(records)-1:
        st.session_state.idx += 1
        st.session_state.needs_sync = True
        st.rerun()
with c3:
    if st.button("💾 保存并跳转下一题", type="primary", use_container_width=True):
        save_current()
        if st.session_state.idx < len(records)-1:
            st.session_state.idx += 1
            st.session_state.needs_sync = True
        st.rerun()
with c4:
    st.info(f"第 {st.session_state.idx + 1} 题")

# 主界面布局
left, right = st.columns([1.6, 1], gap="medium")

with left:
    st.subheader("📝 题目详情")
    with st.container(height=panel_h, border=True):
        st.info(f"**ID:** {curr_item.get('id')} | **题型:** {curr_item.get('type')}")
        
        st.markdown("#### 【题干】")
        render_rich_text(curr_item.get("stem"))
        for img in curr_item.get("stem_images", []):
            st.image(str(BASE_DIR/img) if not Path(img).is_absolute() else img, width=img_w)
            
        if curr_item.get("options"):
            st.markdown("#### 【选项】")
            for opt in curr_item.get("options", []):
                st.write(f"**{opt.get('index')}**:")
                render_rich_text(opt.get("text"))
                
        st.markdown("#### 【答案】")
        st.success(curr_item.get("answer"))
        
        st.markdown("#### 【解析】")
        render_rich_text(curr_item.get("analysis"))
        for img in curr_item.get("analysis_images", []):
            st.image(str(BASE_DIR/img) if not Path(img).is_absolute() else img, width=img_w)

with right:
    st.subheader("🎯 标注工作区")
    with st.container(height=panel_h, border=True):
        # 差异状态显示
        if check_diff():
            st.warning("⚠️ 检测到未保存的修改")
        else:
            st.success("✅ 数据已同步至本地缓存")
            
        with st.expander("🤖 模型建议参考", expanded=True):
            st.write(f"**Bloom:** {curr_item.get('bloom_level')}")
            st.write(f"**主素养:** {curr_item.get('core_literacy_primary')}")
            st.write(f"**候选:** {', '.join(curr_item.get('core_literacy_candidates', []))}")
            if st.button("🪄 一键采纳建议", use_container_width=True):
                st.session_state.ebloom = curr_item.get('bloom_level') or BLOOM_LEVELS[0]
                st.session_state.eprimary = curr_item.get('core_literacy_primary') or CORE_LITERACIES[0]
                st.session_state.ecand = curr_item.get('core_literacy_candidates') or []
                st.session_state.eaccept = True
                st.rerun()

        st.divider()
        
        st.radio("Bloom 认知层级", BLOOM_LEVELS, key="ebloom", horizontal=True)
        st.text_area("Bloom 备注", key="ecomm_b", height=80, placeholder="若层级有偏向请注明...")
        
        st.divider()
        
        st.selectbox("核心素养主标签", CORE_LITERACIES, key="eprimary")
        st.multiselect("核心素养候选 (Max 3)", CORE_LITERACIES, key="ecand", max_selections=3)
        st.text_area("素养备注", key="ecomm_c", height=80)
        
        st.checkbox("确认本题标注已完成", key="eaccept")
        
        cols = st.columns(2)
        with cols[0]:
            if st.button("💾 仅保存本题", use_container_width=True):
                save_current()
                st.rerun()
        with cols[1]:
            if st.button("🔄 还原已存记录", use_container_width=True):
                st.session_state.needs_sync = True
                st.rerun()
        
        st.markdown('<div class="small-muted">提示：每次点击“保存”或“跳转”都会同步到本地 .autosave 文件夹，安全可靠。</div>', unsafe_allow_html=True)
