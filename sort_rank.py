import random
import streamlit as st

# =============== 排序逻辑相关函数 ===============

def init_ranking_state(options):
    """用给定的 options 初始化排序状态"""
    options = options[:]  # 防止修改原列表
    random.shuffle(options)

    st.session_state.total = len(options)          # 总选项数
    st.session_state.remaining = options[1:]       # 剩余待插入
    st.session_state.ranked = [options[0]]         # 已排好序的列表，先放第一个
    st.session_state.current_item = None           # 当前正在插入的选项
    st.session_state.low = 0                       # 二分下界
    st.session_state.high = 0                      # 二分上界
    st.session_state.comparisons = 0               # 比较次数
    st.session_state.processed = 1                 # 已插入的数量（第一个默认插入）
    st.session_state.finished = False              # 是否全部结束
    st.session_state.started = True                # 已经开始排序


def ensure_ranking_initialized():
    """根据当前配置检查是否需要初始化排序"""
    if not st.session_state.get("started"):
        return

    # 如果还没设置 total，说明还没初始化
    if "total" not in st.session_state:
        options = get_current_options_list()
        if len(options) >= 2:
            init_ranking_state(options)


def prepare_next_item():
    """如果当前没有要插入的选项，就从 remaining 中取一个"""
    if st.session_state.current_item is None:
        if st.session_state.remaining:
            st.session_state.current_item = st.session_state.remaining.pop(0)
            st.session_state.low = 0
            st.session_state.high = len(st.session_state.ranked)
        else:
            st.session_state.finished = True


def handle_choice(prefer_left: bool):
    """处理一次 A/B 选择"""
    if st.session_state.finished:
        return

    low = st.session_state.low
    high = st.session_state.high
    mid = (low + high) // 2

    st.session_state.comparisons += 1

    if prefer_left:
        # 更喜欢左边（current_item），应该往前插
        st.session_state.high = mid
    else:
        # 更喜欢右边（ranked[mid]），current_item 往后插
        st.session_state.low = mid + 1

    # 二分结束，确定插入位置
    if st.session_state.low >= st.session_state.high:
        insert_pos = st.session_state.low
        st.session_state.ranked.insert(insert_pos, st.session_state.current_item)
        st.session_state.current_item = None
        st.session_state.processed += 1

    # 重新渲染页面，给出下一对
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()


# =============== 配置相关函数 ===============

def get_current_options_list():
    """从 text_area 文本解析出选项列表"""
    text = st.session_state.get("options_text", "")
    lines = [line.strip() for line in text.splitlines()]
    options = [line for line in lines if line]  # 去掉空行
    return options


def reset_ranking_only():
    """重新开始排序（保留当前主题与选项）"""
    options = get_current_options_list()
    if len(options) < 2:
        st.warning("选项数量至少需要 2 个才能排序。")
        return
    init_ranking_state(options)
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()


def reset_all():
    """彻底重置所有状态，回到初始"""
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()


# =============== 主应用 ===============

def main():
    st.set_page_config(
        page_title="偏好排序小工具",
        page_icon="🎯",
        layout="wide",
    )

    st.title("🎯 偏好排序小工具（自定义主题 & 选项）")

    # --------- 步骤 1：输入主题 & 选项 ---------
    st.markdown("**步骤 1：先在左侧定义你要排序的「主题」和「候选项」**")

    col_left, col_right = st.columns([1.1, 1.9])

    with col_left:
        theme_default = st.session_state.get("theme", "华语男歌手偏好排序")
        theme = st.text_input("主题名称（例：华语男歌手偏好排序）", value=theme_default)
        st.session_state.theme = theme if theme.strip() else "我的偏好排序"

        options_text_default = st.session_state.get("options_text", "")
        st.session_state.options_text = st.text_area(
            "候选项（每行一个）",
            value=options_text_default,
            height=260,
            placeholder="例：\n张学友\n刘德华\n周杰伦\n陈奕迅\n...",
        )

        options = get_current_options_list()
        st.caption(f"当前已输入 {len(options)} 个候选项。")

        btn_start = st.button("✅ 开始 / 重置排序（使用上面的主题和选项）")
        if btn_start:
            if len(options) < 2:
                st.warning("请至少输入 2 个候选项再开始排序。")
            else:
                init_ranking_state(options)
                try:
                    st.rerun()
                except AttributeError:
                    st.experimental_rerun()

        st.button("🧹 全部清空（主题 + 选项 + 排序记录）", on_click=reset_all)

        # 展示候选项清单（方便检查）
        with st.expander("📋 当前候选项列表（只展示，不排序）", expanded=False):
            if options:
                for i, name in enumerate(options, 1):
                    st.write(f"{i}. {name}")
            else:
                st.write("还没有输入任何候选项。")

    # --------- 步骤 2：排序过程 / 结果展示 ---------
    with col_right:
        st.markdown("**步骤 2：通过一系列 1v1 选择，得出总排名**")

        # 根据配置初始化排序状态（如果需要）
        ensure_ranking_initialized()

        # 没有开始排序时，给点提示
        if not st.session_state.get("started"):
            st.info("在左边输入主题和至少 2 个候选项，然后点击“开始 / 重置排序”即可。")
            return

        # 已经开始排序：
        theme_shown = st.session_state.get("theme", "我的偏好排序")
        st.subheader(f"当前主题：{theme_shown}")

        # 如果已经结束，展示最终结果
        if st.session_state.get("finished"):
            st.success("🎉 所有比较已完成！下面是你的最终排名：")

            for i, name in enumerate(st.session_state.ranked, 1):
                st.write(f"{i}. {name}")

            st.caption(
                f"✅ 总共插入了 {st.session_state.total} 个选项，"
                f"比较次数：{st.session_state.comparisons} 次。"
            )

            col_button1, col_button2 = st.columns(2)
            with col_button1:
                st.button("🔁 用同一组选项重新排序一次", on_click=reset_ranking_only)
            with col_button2:
                st.button("✏️ 回到左侧编辑主题 / 选项（然后再点开始）")

            return

        # 正在排序过程
        prepare_next_item()
        if st.session_state.finished:
            # 如果刚准备完就结束了，再 rerun 一次进入结果界面
            try:
                st.rerun()
            except AttributeError:
                st.experimental_rerun()
            return

        current = st.session_state.current_item
        low = st.session_state.low
        high = st.session_state.high
        mid = (low + high) // 2
        opponent = st.session_state.ranked[mid]

        # 进度条 & 状态信息
        progress = st.session_state.processed / st.session_state.total
        st.progress(progress)
        st.caption(
            f"已插入 {st.session_state.processed} / {st.session_state.total} 个选项，"
            f"已比较 {st.session_state.comparisons} 次。"
        )

        st.markdown("### 请选择，你**更喜欢 / 更偏好**哪一个？")

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("#### 选项 A")
            st.markdown(f"### ✳️ {current}")
            if st.button("更喜欢 A", key="btn_left"):
                handle_choice(prefer_left=True)

        with c2:
            st.markdown("#### 选项 B")
            st.markdown(f"### 🔹 {opponent}")
            if st.button("更喜欢 B", key="btn_right"):
                handle_choice(prefer_left=False)

        # 展示当前临时排序
        with st.expander("📊 当前临时排序（从偏好到不那么偏好）", expanded=False):
            for i, name in enumerate(st.session_state.ranked, 1):
                st.write(f"{i}. {name}")


if __name__ == "__main__":
    main()
