import streamlit as st
import json
import os

# ==========================================
# 1. 页面配置与初始化
# ==========================================
st.set_page_config(page_title="智能题库标注系统", layout="wide", page_icon="📝")

DATA_DIR = "data"
TEACHERS = ["teacher_1", "teacher_2", "teacher_3"]

# 初始化 Session State
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'current_teacher' not in st.session_state:
    st.session_state.current_teacher = TEACHERS[0]

# ==========================================
# 2. 数据处理函数
# ==========================================
def load_data(teacher_name):
    """加载指定老师的 JSON 数据"""
    file_path = os.path.join(DATA_DIR, f"{teacher_name}.json")
    if not os.path.exists(file_path):
        # 如果文件不存在，返回空列表并提示
        st.error(f"找不到文件: {file_path}。请确保数据放置在正确的目录下。")
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(teacher_name, data):
    """保存数据到对应的 JSON 文件"""
    file_path = os.path.join(DATA_DIR, f"{teacher_name}.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==========================================
# 3. 侧边栏：全局控制与导航
# ==========================================
with st.sidebar:
    st.title("⚙️ 标注控制台")
    
    # 切换老师（当切换老师时，将进度重置为0）
    selected_teacher = st.selectbox(
        "🧑‍🏫 选择当前标注教师", 
        TEACHERS, 
        index=TEACHERS.index(st.session_state.current_teacher)
    )
    if selected_teacher != st.session_state.current_teacher:
        st.session_state.current_teacher = selected_teacher
        st.session_state.current_index = 0
        st.rerun()

    # 加载当前老师的数据
    data = load_data(st.session_state.current_teacher)
    total_questions = len(data)

    if total_questions == 0:
        st.warning("暂无数据")
        st.stop()

    st.divider()
    
    # 进度指示器
    annotated_count = sum(1 for item in data if item.get("is_annotated", False))
    st.metric("已标注数量", f"{annotated_count} / {total_questions}")
    st.progress(annotated_count / total_questions if total_questions > 0 else 0)

    # 题目快速跳转
    jump_index = st.number_input(
        "跳转到题目序号 (1-{})".format(total_questions), 
        min_value=1, 
        max_value=total_questions, 
        value=st.session_state.current_index + 1
    ) - 1
    if jump_index != st.session_state.current_index:
        st.session_state.current_index = jump_index
        st.rerun()

# ==========================================
# 4. 主工作区：题目展示与标注表单
# ==========================================
current_q = data[st.session_state.current_index]

# 顶部导航按钮
col_prev, col_info, col_next = st.columns([1, 8, 1])
with col_prev:
    if st.button("⬅️ 上一题", use_container_width=True) and st.session_state.current_index > 0:
        st.session_state.current_index -= 1
        st.rerun()
with col_info:
    st.markdown(f"<h3 style='text-align: center;'>当前题目：{st.session_state.current_index + 1} / {total_questions}</h3>", unsafe_allow_html=True)
with col_next:
    if st.button("下一题 ➡️", use_container_width=True) and st.session_state.current_index < total_questions - 1:
        st.session_state.current_index += 1
        st.rerun()

st.divider()

# 左右分栏：左侧看题，右侧打标
col_content, col_annotation = st.columns([6, 4], gap="large")

# --- 左侧：题目详情展示 ---
with col_content:
    st.subheader("📖 题目详情")
    st.markdown(f"**【题干】**\n\n{current_q.get('stem', '无题干')}")
    
    # 显示题干图片 (如果有)
    for img_path in current_q.get("stem_images", []):
        if os.path.exists(img_path):
            st.image(img_path, caption="题干配图")
        else:
            st.warning(f"图片未找到: {img_path}")

    st.markdown("**【选项】**")
    for opt in current_q.get("options", []):
        st.markdown(f"- **{opt['index']}**: {opt['text']}")
        # 选项图片暂略，逻辑同上

    st.markdown(f"**【标准答案】** `{current_q.get('answer', '无')}`")
    
    with st.expander("查看详细解析及元数据", expanded=False):
        st.markdown(f"**解析:**\n\n{current_q.get('analysis', '无解析')}")
        st.markdown(f"**当前难度:** {current_q.get('difficulty', '未知')}")
        st.markdown(f"**知识点:** {', '.join(current_q.get('knowledges', []))}")
        st.markdown(f"**认知能力:** {', '.join(current_q.get('abilities', []))}")

# --- 右侧：标注操作区 ---
with col_annotation:
    st.subheader("✍️ 专家标注区")
    
    # 使用 st.form 确保点击“保存”时统一收集数据，避免频繁刷新
    with st.form(key=f"annotation_form_{st.session_state.current_index}"):
        
        # 标注字段 1：质量评分 (示例)
        quality_score = st.slider(
            "1. 题目整体质量评分 (1-5分)", 
            1, 5, 
            value=current_q.get("annotation_quality", 3)
        )
        
        # 标注字段 2：认知维度修正 (示例，结合教育测量学)
        cognitive_levels = ["记忆", "理解", "应用", "分析", "评价", "创造"]
        default_ability = current_q.get("annotation_ability", current_q.get("abilities", ["理解"])[0])
        if default_ability not in cognitive_levels:
            default_ability = "理解"
            
        revised_ability = st.selectbox(
            "2. 修正认知能力维度 (Bloom's Taxonomy)", 
            cognitive_levels,
            index=cognitive_levels.index(default_ability)
        )
        
        # 标注字段 3：标签体系映射状态
        label_status = st.radio(
            "3. 知识点与本校课标贴合度",
            ["完全贴合", "部分贴合", "需修改/不贴合"],
            index=["完全贴合", "部分贴合", "需修改/不贴合"].index(current_q.get("annotation_fit", "完全贴合"))
        )

        # 标注字段 4：文本反馈
        feedback = st.text_area(
            "4. 专家修改意见 (选填)", 
            value=current_q.get("annotation_feedback", ""),
            height=100
        )

        submit_btn = st.form_submit_button("💾 保存当前标注并进入下一题", type="primary", use_container_width=True)

    # 处理表单提交逻辑
    if submit_btn:
        # 更新当前数据字典
        current_q["annotation_quality"] = quality_score
        current_q["annotation_ability"] = revised_ability
        current_q["annotation_fit"] = label_status
        current_q["annotation_feedback"] = feedback
        current_q["is_annotated"] = True  # 标记为已处理
        
        # 保存回 JSON
        data[st.session_state.current_index] = current_q
        save_data(st.session_state.current_teacher, data)
        
        st.toast("✅ 标注已保存！", icon="🎉")
        
        # 自动跳到下一题 (如果是最后一题则不跳)
        if st.session_state.current_index < total_questions - 1:
            st.session_state.current_index += 1
            st.rerun()
        else:
            st.success("🎉 恭喜！您已完成所有题目的标注！")
