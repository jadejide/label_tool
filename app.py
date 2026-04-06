"""
教育题目标注工具
支持Bloom层级和核心素养标注
"""

import streamlit as st
import json
import os
import pandas as pd
from pathlib import Path
from PIL import Image
import base64
from datetime import datetime

# ============== 配置 ==============
st.set_page_config(
    page_title="教育题目标注工具",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============== 常量定义 ==============
BLOOM_LEVELS = ["记忆", "理解", "应用", "分析", "评价", "创造"]

CORE_LITERACY_OPTIONS = [
    "运算能力", "模型观念", "推理能力", "抽象能力", 
    "几何直观", "空间观念", "数据观念", "应用意识", "创新意识"
]

QUESTION_TYPES = {
    "填空题": "📝",
    "选择题": "🔘",
    "解答题": "📋",
    "计算题": "🔢",
    "证明题": "📐",
    "应用题": "🔧"
}

# ============== 初始化Session State ==============
def init_session_state():
    """初始化session state变量"""
    defaults = {
        'data': None,
        'current_index': 0,
        'annotations': {},
        'file_loaded': False,
        'filename': None,
        'auto_save_enabled': True,
        'show_help': False,
        'filter_unannotated': False,
        'jump_to_index': 0,
        'last_saved': None,
        'show_model_ref': True,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ============== CSS样式 ==============
st.markdown("""
<style>
    /* 整体布局 */
    .main > div {
        padding-top: 1rem;
    }
    
    /* 题目卡片 */
    .question-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        color: white;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* 标注区样式 */
    .annotation-section {
        background: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        border: 2px solid #e9ecef;
    }
    
    /* 模型参考样式 */
    .model-ref {
        background: #e3f2fd;
        padding: 10px 15px;
        border-radius: 8px;
        border-left: 4px solid #2196f3;
        margin: 10px 0;
    }
    
    /* 进度条 */
    .progress-container {
        background: #e9ecef;
        border-radius: 10px;
        height: 20px;
        overflow: hidden;
    }
    
    .progress-bar {
        background: linear-gradient(90deg, #4caf50, #8bc34a);
        height: 100%;
        border-radius: 10px;
        transition: width 0.3s ease;
    }
    
    /* 按钮样式 */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 500 !important;
    }
    
    /* 信息标签 */
    .info-tag {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 500;
        margin-right: 8px;
        margin-bottom: 8px;
    }
    
    .tag-type { background: #e3f2fd; color: #1976d2; }
    .tag-difficulty-easy { background: #e8f5e9; color: #388e3c; }
    .tag-difficulty-medium { background: #fff3e0; color: #f57c00; }
    .tag-difficulty-hard { background: #ffebee; color: #d32f2f; }
    .tag-score { background: #f3e5f5; color: #7b1fa2; }
    .tag-grade { background: #e0f2f1; color: #00796b; }
    
    /* LaTeX公式样式 */
    .latex-formula {
        background: #fafafa;
        padding: 15px;
        border-radius: 8px;
        font-family: 'Times New Roman', serif;
        font-size: 16px;
        overflow-x: auto;
    }
    
    /* 滚动区域 */
    .scroll-area {
        max-height: 70vh;
        overflow-y: auto;
        padding-right: 10px;
    }
    
    /* 自定义滚动条 */
    .scroll-area::-webkit-scrollbar {
        width: 8px;
    }
    
    .scroll-area::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 4px;
    }
    
    .scroll-area::-webkit-scrollbar-thumb {
        background: #888;
        border-radius: 4px;
    }
    
    /* 成功提示 */
    .success-toast {
        position: fixed;
        top: 20px;
        right: 20px;
        background: #4caf50;
        color: white;
        padding: 15px 25px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 9999;
        animation: slideIn 0.3s ease;
    }
    
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    /* 必填标记 */
    .required::after {
        content: " *";
        color: #f44336;
    }
    
    /* 侧边栏样式 */
    .sidebar-info {
        background: #f5f5f5;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 15px;
    }
    
    /* 图片容器 */
    .image-container {
        text-align: center;
        margin: 15px 0;
    }
    
    .image-container img {
        max-width: 100%;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# ============== 工具函数 ==============

def load_json_file(file_path):
    """加载JSON文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"加载文件失败: {e}")
        return None

def get_difficulty_color(difficulty):
    """根据难度返回颜色类名"""
    difficulty_map = {
        "易": "tag-difficulty-easy",
        "中": "tag-difficulty-medium", 
        "难": "tag-difficulty-hard"
    }
    return difficulty_map.get(difficulty, "tag-difficulty-medium")

def format_latex(text):
    """格式化LaTeX文本，将$...$转换为st.latex可识别的格式"""
    if not text:
        return ""
    # 替换换行符
    text = text.replace('\\n', '\n')
    return text

def display_images(image_paths, base_path):
    """显示题目图片"""
    if not image_paths:
        return
    
    cols = st.columns(min(len(image_paths), 2))
    for idx, img_path in enumerate(image_paths):
        full_path = os.path.join(base_path, img_path)
        if os.path.exists(full_path):
            with cols[idx % 2]:
                try:
                    img = Image.open(full_path)
                    st.image(img, caption=f"图 {idx + 1}", use_column_width=True)
                except Exception as e:
                    st.warning(f"无法加载图片: {img_path}")
        else:
            st.warning(f"图片不存在: {img_path}")

def get_annotation_status(index):
    """获取标注状态"""
    annotation = st.session_state.annotations.get(index, {})
    bloom = annotation.get('bloom_level', '')
    literacy = annotation.get('core_literacy', [])
    
    if bloom and literacy:
        return "✅ 已标注"
    elif bloom or literacy:
        return "⚠️ 部分标注"
    else:
        return "❌ 未标注"

def is_fully_annotated(index):
    """检查是否完成标注"""
    annotation = st.session_state.annotations.get(index, {})
    return bool(annotation.get('bloom_level')) and bool(annotation.get('core_literacy'))

def save_annotation(index, bloom_level, core_literacy, bloom_reason='', literacy_reason=''):
    """保存标注"""
    st.session_state.annotations[index] = {
        'bloom_level': bloom_level,
        'core_literacy': core_literacy,
        'bloom_reason': bloom_reason,
        'literacy_reason': literacy_reason,
        'annotated_at': datetime.now().isoformat()
    }
    st.session_state.last_saved = datetime.now().strftime("%H:%M:%S")

def get_progress():
    """获取标注进度"""
    if not st.session_state.data:
        return 0, 0
    total = len(st.session_state.data)
    completed = sum(1 for i in range(total) if is_fully_annotated(i))
    return completed, total

def export_annotations(format_type='json'):
    """导出标注结果"""
    if not st.session_state.data:
        return None
    
    export_data = []
    for idx, item in enumerate(st.session_state.data):
        annotation = st.session_state.annotations.get(idx, {})
        export_item = {
            'id': item.get('id', ''),
            'type': item.get('type', ''),
            'difficulty': item.get('difficulty', ''),
            'bloom_level': annotation.get('bloom_level', ''),
            'bloom_reason': annotation.get('bloom_reason', ''),
            'core_literacy': ','.join(annotation.get('core_literacy', [])),
            'literacy_reason': annotation.get('literacy_reason', ''),
            'model_bloom': item.get('bloom_level', ''),
            'model_literacy': ','.join(item.get('core_literacy_candidates', [])),
            'annotated_at': annotation.get('annotated_at', '')
        }
        export_data.append(export_item)
    
    if format_type == 'json':
        return json.dumps(export_data, ensure_ascii=False, indent=2)
    else:
        df = pd.DataFrame(export_data)
        return df.to_csv(index=False)

def get_unannotated_indices():
    """获取未标注的题目索引"""
    if not st.session_state.data:
        return []
    return [i for i in range(len(st.session_state.data)) if not is_fully_annotated(i)]

# ============== 侧边栏 ==============
with st.sidebar:
    st.title("📚 标注工具")
    st.markdown("---")
    
    # 文件选择
    st.subheader("📁 选择数据文件")
    data_dir = Path("data")
    if data_dir.exists():
        json_files = list(data_dir.glob("*.json"))
        if json_files:
            file_options = [f.name for f in json_files]
            selected_file = st.selectbox(
                "选择文件",
                file_options,
                index=0 if not st.session_state.filename else file_options.index(st.session_state.filename) if st.session_state.filename in file_options else 0
            )
            
            if st.button("📂 加载文件", type="primary", use_container_width=True):
                file_path = data_dir / selected_file
                data = load_json_file(file_path)
                if data:
                    st.session_state.data = data
                    st.session_state.filename = selected_file
                    st.session_state.file_loaded = True
                    st.session_state.current_index = 0
                    st.session_state.annotations = {}
                    st.success(f"✅ 成功加载 {len(data)} 道题目")
                    st.rerun()
        else:
            st.warning("data目录下没有找到JSON文件")
    else:
        st.warning("data目录不存在")
    
    st.markdown("---")
    
    # 进度显示
    if st.session_state.file_loaded and st.session_state.data:
        completed, total = get_progress()
        progress_pct = (completed / total * 100) if total > 0 else 0
        
        st.subheader("📊 标注进度")
        st.progress(progress_pct / 100)
        st.markdown(f"**{completed}** / {total} ({progress_pct:.1f}%)")
        
        # 快速跳转
        st.markdown("---")
        st.subheader("🚀 快速跳转")
        
        # 筛选未标注
        st.session_state.filter_unannotated = st.checkbox(
            "仅显示未标注", 
            value=st.session_state.filter_unannotated
        )
        
        if st.session_state.filter_unannotated:
            unannotated = get_unannotated_indices()
            if unannotated:
                current_unannotated_idx = unannotated.index(st.session_state.current_index) if st.session_state.current_index in unannotated else 0
                selected_unannotated = st.selectbox(
                    "未标注题目",
                    [f"第 {i+1} 题 - {st.session_state.data[i].get('type', '未知类型')}" for i in unannotated],
                    index=current_unannotated_idx if current_unannotated_idx < len(unannotated) else 0
                )
                if selected_unannotated:
                    new_idx = unannotated[[f"第 {i+1} 题" in selected_unannotated for i in unannotated].index(True)]
                    if new_idx != st.session_state.current_index:
                        st.session_state.current_index = new_idx
                        st.rerun()
            else:
                st.success("🎉 所有题目已标注完成！")
        else:
            jump_to = st.number_input(
                "跳转到题号",
                min_value=1,
                max_value=len(st.session_state.data),
                value=st.session_state.current_index + 1
            )
            if st.button("跳转", use_container_width=True):
                st.session_state.current_index = jump_to - 1
                st.rerun()
        
        # 设置
        st.markdown("---")
        st.subheader("⚙️ 设置")
        st.session_state.show_model_ref = st.checkbox(
            "显示模型参考意见", 
            value=st.session_state.show_model_ref
        )
        st.session_state.auto_save_enabled = st.checkbox(
            "启用自动保存", 
            value=st.session_state.auto_save_enabled
        )
        
        # 导出
        st.markdown("---")
        st.subheader("💾 导出结果")
        
        export_format = st.radio("格式", ["JSON", "CSV"])
        
        if st.button("📥 下载标注结果", type="primary", use_container_width=True):
            if completed == total:
                export_data = export_annotations('json' if export_format == "JSON" else 'csv')
                if export_data:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"annotations_{st.session_state.filename.replace('.json', '')}_{timestamp}.{export_format.lower()}"
                    
                    if export_format == "JSON":
                        st.download_button(
                            label="⬇️ 点击下载 JSON",
                            data=export_data,
                            file_name=filename,
                            mime="application/json",
                            use_container_width=True
                        )
                    else:
                        st.download_button(
                            label="⬇️ 点击下载 CSV",
                            data=export_data,
                            file_name=filename,
                            mime="text/csv",
                            use_container_width=True
                        )
            else:
                st.error(f"⚠️ 还有 {total - completed} 道题未标注，完成后才能导出")
        
        # 快捷键说明
        st.markdown("---")
        with st.expander("⌨️ 快捷键说明"):
            st.markdown("""
            - **A** - 上一题
            - **D** - 下一题
            - **S** - 保存并下一题
            - **1-6** - 快速选择Bloom层级
            """)

# ============== 主界面 ==============
if not st.session_state.file_loaded or not st.session_state.data:
    # 欢迎页面
    st.markdown("""
    <div style="text-align: center; padding: 50px;">
        <h1>📚 教育题目标注工具</h1>
        <p style="font-size: 18px; color: #666;">
            请在左侧选择数据文件开始标注
        </p>
        <div style="margin-top: 30px; padding: 20px; background: #f5f5f5; border-radius: 10px; display: inline-block;">
            <h4>使用步骤：</h4>
            <ol style="text-align: left;">
                <li>在左侧选择要标注的JSON文件</li>
                <li>点击"加载文件"按钮</li>
                <li>查看题目内容并进行标注</li>
                <li>点击"保存并下一题"继续</li>
                <li>完成后导出标注结果</li>
            </ol>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    # 获取当前题目
    current_idx = st.session_state.current_index
    total = len(st.session_state.data)
    current_question = st.session_state.data[current_idx]
    
    # 顶部导航栏
    col_nav1, col_nav2, col_nav3, col_nav4 = st.columns([1, 1, 2, 1])
    
    with col_nav1:
        if st.button("⬅️ 上一题 (A)", use_container_width=True, disabled=current_idx == 0):
            st.session_state.current_index = max(0, current_idx - 1)
            st.rerun()
    
    with col_nav2:
        if st.button("下一题 (D) ➡️", use_container_width=True, disabled=current_idx >= total - 1):
            st.session_state.current_index = min(total - 1, current_idx + 1)
            st.rerun()
    
    with col_nav3:
        st.markdown(f"""
        <div style="text-align: center; padding: 10px;">
            <span style="font-size: 20px; font-weight: bold;">
                第 {current_idx + 1} / {total} 题
            </span>
            <span style="margin-left: 15px; color: {'#4caf50' if is_fully_annotated(current_idx) else '#f44336'};">
                {get_annotation_status(current_idx)}
            </span>
        </div>
        """, unsafe_allow_html=True)
    
    with col_nav4:
        if st.session_state.last_saved:
            st.caption(f"上次保存: {st.session_state.last_saved}")
    
    st.markdown("---")
    
    # 主内容区 - 两列布局
    col_question, col_annotation = st.columns([3, 2])
    
    # ============== 左侧：题目展示区 ==============
    with col_question:
        st.subheader("📖 题目内容")
        
        # 题目信息标签
        q_type = current_question.get('type', '未知')
        q_difficulty = current_question.get('difficulty', '未知')
        q_score = current_question.get('score', 0)
        q_grades = ', '.join(current_question.get('grades', []))
        
        type_icon = QUESTION_TYPES.get(q_type, '📝')
        
        st.markdown(f"""
        <div style="margin-bottom: 15px;">
            <span class="info-tag tag-type">{type_icon} {q_type}</span>
            <span class="info-tag {get_difficulty_color(q_difficulty)}">难度: {q_difficulty}</span>
            <span class="info-tag tag-score">分值: {q_score}分</span>
            <span class="info-tag tag-grade">年级: {q_grades}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # 题干
        with st.container():
            st.markdown("**【题干】**")
            stem = current_question.get('normalized_stem', '')
            if stem:
                st.markdown(format_latex(stem))
            
            # 显示题干图片
            stem_images = current_question.get('stem_images', [])
            if stem_images:
                display_images(stem_images, '.')
        
        # 选项（如果是选择题）
        options = current_question.get('options', [])
        if options:
            st.markdown("**【选项】**")
            for i, opt in enumerate(options):
                option_letter = chr(65 + i)  # A, B, C, D...
                st.markdown(f"**{option_letter}.** {opt}")
        
        # 答案
        with st.expander("💡 查看答案"):
            answer = current_question.get('answer', '')
            st.markdown(f"**答案：** {answer}")
        
        # 解析
        with st.expander("📖 查看解析"):
            analysis = current_question.get('normalized_analysis', '')
            if analysis:
                st.markdown(format_latex(analysis))
            
            # 显示解析图片
            analysis_images = current_question.get('analysis_images', [])
            if analysis_images:
                display_images(analysis_images, '.')
        
        # 知识点
        with st.expander("📚 知识点"):
            knowledges = current_question.get('knowledges', [])
            bnu_knowledges = current_question.get('bnu_knowledges', [])
            xkb_knowledges = current_question.get('xkb_knowledges', [])
            
            if knowledges:
                st.markdown("**知识点：** " + ", ".join(knowledges))
            if bnu_knowledges:
                st.markdown("**北师大版：** " + ", ".join(bnu_knowledges))
            if xkb_knowledges:
                st.markdown("**新课标：** " + ", ".join(xkb_knowledges))
        
        # 能力维度
        abilities = current_question.get('abilities', [])
        if abilities:
            st.markdown(f"**能力维度：** {', '.join(abilities)}")
    
    # ============== 右侧：标注区 ==============
    with col_annotation:
        st.subheader("🏷️ 标注区")
        
        # 获取当前标注
        current_annotation = st.session_state.annotations.get(current_idx, {})
        current_bloom = current_annotation.get('bloom_level', '')
        current_literacy = current_annotation.get('core_literacy', [])
        current_bloom_reason = current_annotation.get('bloom_reason', '')
        current_literacy_reason = current_annotation.get('literacy_reason', '')
        
        # Bloom层级标注
        st.markdown("**<span class='required'>Bloom认知层级</span>**", unsafe_allow_html=True)
        
        # 模型参考意见
        if st.session_state.show_model_ref:
            model_bloom = current_question.get('bloom_level', '')
            model_bloom_reason = current_question.get('bloom_reason', '')
            if model_bloom:
                st.markdown(f"""
                <div class="model-ref">
                    <strong>🤖 模型参考：</strong>{model_bloom}<br/>
                    <small>理由：{model_bloom_reason}</small>
                </div>
                """, unsafe_allow_html=True)
        
        bloom_level = st.radio(
            "选择Bloom层级",
            BLOOM_LEVELS,
            index=BLOOM_LEVELS.index(current_bloom) if current_bloom in BLOOM_LEVELS else None,
            horizontal=True,
            label_visibility="collapsed"
        )
        
        # Bloom层级说明
        with st.expander("ℹ️ Bloom层级说明"):
            st.markdown("""
            - **记忆**：回忆事实、术语、基本概念
            - **理解**：理解含义、解释概念
            - **应用**：在新情境中使用知识
            - **分析**：分解信息、发现关系
            - **评价**：做出判断、评估价值
            - **创造**：整合元素形成新整体
            """)
        
        # Bloom标注理由
        bloom_reason = st.text_area(
            "Bloom标注理由（可选）",
            value=current_bloom_reason,
            placeholder="请说明为什么选择这个Bloom层级...",
            height=80
        )
        
        st.markdown("---")
        
        # 核心素养标注
        st.markdown("**<span class='required'>核心素养</span>**", unsafe_allow_html=True)
        
        # 模型参考意见
        if st.session_state.show_model_ref:
            model_literacy_primary = current_question.get('core_literacy_primary', '')
            model_literacy_candidates = current_question.get('core_literacy_candidates', [])
            model_literacy_reason = current_question.get('core_literacy_reason', '')
            if model_literacy_primary or model_literacy_candidates:
                st.markdown(f"""
                <div class="model-ref">
                    <strong>🤖 模型参考：</strong><br/>
                    主要素养：{model_literacy_primary}<br/>
                    候选素养：{', '.join(model_literacy_candidates)}<br/>
                    <small>理由：{model_literacy_reason}</small>
                </div>
                """, unsafe_allow_html=True)
        
        core_literacy = st.multiselect(
            "选择核心素养（可多选）",
            CORE_LITERACY_OPTIONS,
            default=current_literacy
        )
        
        # 核心素养理由
        literacy_reason = st.text_area(
            "核心素养标注理由（可选）",
            value=current_literacy_reason,
            placeholder="请说明为什么选择这些核心素养...",
            height=80
        )
        
        st.markdown("---")
        
        # 操作按钮
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("💾 保存", use_container_width=True, type="secondary"):
                if bloom_level and core_literacy:
                    save_annotation(current_idx, bloom_level, core_literacy, bloom_reason, literacy_reason)
                    st.success("✅ 保存成功！")
                else:
                    st.error("⚠️ 请完成所有必填项！")
        
        with col_btn2:
            if st.button("💾 保存并下一题 (S)", use_container_width=True, type="primary"):
                if bloom_level and core_literacy:
                    save_annotation(current_idx, bloom_level, core_literacy, bloom_reason, literacy_reason)
                    if current_idx < total - 1:
                        st.session_state.current_index = current_idx + 1
                        st.rerun()
                    else:
                        st.balloons()
                        st.success("🎉 恭喜！所有题目已标注完成！")
                else:
                    st.error("⚠️ 请完成所有必填项！")
        
        # 自动保存提示
        if st.session_state.auto_save_enabled:
            # 检查是否有变化，自动保存
            if (bloom_level != current_bloom or 
                set(core_literacy) != set(current_literacy) or
                bloom_reason != current_bloom_reason or
                literacy_reason != current_literacy_reason):
                if bloom_level and core_literacy:
                    save_annotation(current_idx, bloom_level, core_literacy, bloom_reason, literacy_reason)
    
    # ============== 底部：题目列表预览 ==============
    st.markdown("---")
    with st.expander("📋 题目列表预览"):
        # 创建预览表格
        preview_data = []
        for i, q in enumerate(st.session_state.data):
            status = "✅" if is_fully_annotated(i) else "❌"
            preview_data.append({
                "序号": i + 1,
                "状态": status,
                "题型": q.get('type', ''),
                "难度": q.get('difficulty', ''),
                "Bloom": st.session_state.annotations.get(i, {}).get('bloom_level', '-'),
                "核心素养": ', '.join(st.session_state.annotations.get(i, {}).get('core_literacy', [])) or '-'
            })
        
        df_preview = pd.DataFrame(preview_data)
        st.dataframe(df_preview, use_container_width=True, height=300)

# ============== 快捷键JavaScript ==============
st.markdown("""
<script>
document.addEventListener('keydown', function(e) {
    // 忽略输入框中的按键
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
    }
    
    switch(e.key.toLowerCase()) {
        case 'a':
            // 上一题
            window.parent.postMessage({type: 'streamlit:setComponentValue', value: 'prev'}, '*');
            break;
        case 'd':
            // 下一题
            window.parent.postMessage({type: 'streamlit:setComponentValue', value: 'next'}, '*');
            break;
        case 's':
            // 保存并下一题
            window.parent.postMessage({type: 'streamlit:setComponentValue', value: 'save_next'}, '*');
            break;
    }
});
</script>
""", unsafe_allow_html=True)
