"""
Pomodoro Timer —— 番茄工作法计时器

功能概述：
  - 默认提供三种模式：工作(25分钟)、短休息(5分钟)、长休息(15分钟)
  - 支持启动、暂停、恢复、重置计时器
  - 每次工作完成后自动切换到休息模式，每完成 4 个工作时段自动进入长休息
  - 通过自定义环形进度条和数字时钟展示剩余时间
  - 支持自定义各模式的时长（通过 Spinbox 输入分钟数）
  - 配置自动持久化到用户目录下的 .pomodoro_config.json 文件
  - 计时结束时有提示音和弹窗通知
  - 支持窗口置顶

状态机设计：
  IDLE(0) ──start──> RUNNING(1) ──pause──> PAUSED(2) ──resume(start)──> RUNNING(1)
    ^                    │                      │
    └──── reset ─────────┴──────────────────────┘
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import winsound       # Windows 系统提示音 API
from pathlib import Path


class PomodoroApp:
    """番茄钟主应用类，包含 UI、计时逻辑、配置管理。"""

    # ── 默认时长（秒）───────────────────────────────────────────
    WORK = 25 * 60          # 工作时间：25 分钟
    SHORT_BREAK = 5 * 60    # 短休息：5 分钟
    LONG_BREAK = 15 * 60    # 长休息：15 分钟

    # ── 主题色 ──────────────────────────────────────────────────
    COLOR_WORK = "#E53935"           # 工作模式主题色（红色）
    COLOR_SHORT_BREAK = "#43A047"    # 短休息主题色（绿色）
    COLOR_LONG_BREAK = "#1E88E5"     # 长休息主题色（蓝色）
    COLOR_BG = "#1e1e1e"             # 全局背景色（深灰黑）
    COLOR_SURFACE = "#2d2d2d"        # 控件表面色（比背景稍亮）
    COLOR_SURFACE_HOVER = "#3d3d3d"  # 控件悬停色
    COLOR_TEXT = "#ffffff"           # 主文本颜色（白色）
    COLOR_TEXT_SECONDARY = "#aaaaaa" # 次要文本颜色（灰色）
    COLOR_RING_BG = "#3a3a3a"        # 进度环背景轨道颜色

    # ── 模式元数据：统一管理三种模式的颜色、显示名 ──────────────
    # 格式：{ mode_key: (display_name, color_attr) }
    META = {
        "work":        ("Work",        "COLOR_WORK"),
        "short_break": ("Short Break", "COLOR_SHORT_BREAK"),
        "long_break":  ("Long Break",  "COLOR_LONG_BREAK"),
    }

    # ── 计时器状态枚举 ──────────────────────────────────────────
    IDLE = 0       # 空闲：计时器未启动，显示总时长
    RUNNING = 1    # 运行中：每秒倒计时
    PAUSED = 2     # 已暂停：计时停止，保留当前剩余时间

    def __init__(self):
        """初始化窗口、状态变量、UI 和配置。"""
        # ── 主窗口设置 ──
        self.root = tk.Tk()
        self.root.title("Pomodoro Timer")
        self.root.geometry("380x580")                    # 固定窗口大小
        self.root.resizable(False, False)                 # 禁止调整大小
        self.root.configure(bg=self.COLOR_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)  # 关闭时保存配置

        # ── 计时器内部状态 ──
        self.state = self.IDLE            # 当前状态：IDLE / RUNNING / PAUSED
        self.mode = "work"                # 当前模式："work" / "short_break" / "long_break"
        self.remaining = self.WORK        # 当前剩余秒数
        self.total = self.WORK            # 当前模式总秒数（用于进度百分比计算）
        self.work_sessions = 0            # 已完成的工作时段计数（用于判断是否进入长休息）
        self.after_id = None              # tkinter 定时器 ID，用于取消延迟任务

        # ── 加载持久化配置 ──
        self.config_path = Path.home() / ".pomodoro_config.json"
        self.config = self.load_config()

        # ── 构建界面并启动主循环 ──
        self.build_ui()
        self.apply_config()               # 将已保存的配置写入 Spinbox 控件
        self.update_mode_buttons()        # 高亮当前模式的按钮
        self.root.mainloop()              # 进入 tkinter 事件循环（阻塞）

    # ══════════════════════════════════════════════════════════════
    #  UI 构建
    # ══════════════════════════════════════════════════════════════

    def build_ui(self):
        """按从上到下的顺序组装所有 UI 区域。"""
        # 标题
        title = tk.Label(
            self.root, text="Pomodoro",
            font=("Segoe UI", 22, "bold"),
            fg=self.COLOR_TEXT, bg=self.COLOR_BG,
        )
        title.pack(pady=(20, 0))

        self._build_canvas()          # 环形进度条 + 时间文字
        self._build_mode_buttons()    # 模式切换按钮（Work / Short Break / Long Break）
        self._build_controls()        # 控制按钮（Start / Pause / Reset）
        self._build_separator()       # 分割线
        self._build_stats()           # 统计信息（已完成会话数）
        self._build_settings()        # 时长设置（Spinbox）
        self._build_bottom()          # 底部复选框（窗口置顶）

    def _build_canvas(self):
        """
        构建中央圆形进度区域。
        包含三个图层（从下到上）：
          1. 背景环形轨道（灰色）
          2. 前景进度弧（彩色，随剩余时间顺时针缩减）
          3. 数字时间文本 + 模式名称文本
        """
        self.canvas_size = 280
        self.canvas = tk.Canvas(
            self.root, width=self.canvas_size, height=self.canvas_size,
            bg=self.COLOR_BG, highlightthickness=0,  # 去掉默认边框
        )
        self.canvas.pack(pady=8)

        cx = cy = self.canvas_size // 2   # 圆心坐标
        r = 115                            # 半径

        # 绘制背景轨道圆（固定不动）
        self.canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            outline=self.COLOR_RING_BG, width=10,
        )

        # 绘制前景进度弧（初始 extent=359.999 即满环，随倒计时递减）
        # start=90 表示从12点钟方向开始；extent 为顺时针扫过的角度
        self.progress_ring = self.canvas.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            start=90, extent=359.999,
            outline=self.COLOR_WORK, width=10, style="arc",
        )

        # 数字时间标签（居中覆盖在圆环上方）
        self.time_label = tk.Label(
            self.canvas, text="25:00",
            font=("Segoe UI", 38, "bold"),
            fg=self.COLOR_TEXT, bg=self.COLOR_BG,
        )
        self.time_label.place(x=cx, y=cy - 6, anchor="center")

        # 模式名称标签（显示在时间下方）
        self.mode_label = tk.Label(
            self.canvas, text="Work",
            font=("Segoe UI", 11),
            fg=self.COLOR_WORK, bg=self.COLOR_BG,
        )
        self.mode_label.place(x=cx, y=cy + 32, anchor="center")

    def _build_mode_buttons(self):
        """构建三个模式切换按钮：Work、Short Break、Long Break。"""
        frame = tk.Frame(self.root, bg=self.COLOR_BG)
        frame.pack(pady=6)

        self.mode_buttons = {}  # key=模式名称, value=(按钮对象, 主题色)
        modes = [
            ("Work", "work", self.COLOR_WORK),
            ("Short Break", "short_break", self.COLOR_SHORT_BREAK),
            ("Long Break", "long_break", self.COLOR_LONG_BREAK),
        ]
        for text, value, color in modes:
            btn = tk.Button(
                frame, text=text,
                font=("Segoe UI", 9),
                fg=self.COLOR_TEXT, bg=self.COLOR_SURFACE,
                activeforeground=self.COLOR_TEXT, activebackground=color,
                relief="flat", padx=12, pady=5,
                # lambda 默认参数捕获当前 value，避免闭包延迟绑定问题
                command=lambda v=value: self.switch_mode(v),
            )
            btn.pack(side="left", padx=3)
            self.mode_buttons[value] = (btn, color)

    def _build_controls(self):
        """构建 Start / Pause / Reset 三个操作按钮。"""
        frame = tk.Frame(self.root, bg=self.COLOR_BG)
        frame.pack(pady=12)

        # 三个按钮的公共样式
        base = {
            "font": ("Segoe UI", 11, "bold"),
            "relief": "flat", "padx": 22, "pady": 7,
            "fg": self.COLOR_TEXT,
            "activeforeground": self.COLOR_TEXT,
        }

        self.start_btn = tk.Button(
            frame, text="Start", bg="#2E7D32",
            activebackground="#388E3C",
            command=self.start, **base,
        )
        self.start_btn.pack(side="left", padx=4)

        self.pause_btn = tk.Button(
            frame, text="Pause", bg="#F57F17",
            activebackground="#F9A825",
            command=self.pause, state="disabled",  # 初始禁用，只有运行中才能暂停
            **base,
        )
        self.pause_btn.pack(side="left", padx=4)

        self.reset_btn = tk.Button(
            frame, text="Reset", bg="#616161",
            activebackground="#757575",
            command=self.reset, **base,
        )
        self.reset_btn.pack(side="left", padx=4)

    def _build_separator(self):
        """横向分割线，分隔控制区与统计/设置区。"""
        sep = tk.Frame(self.root, height=1, bg=self.COLOR_SURFACE)
        sep.pack(fill="x", padx=40)

    def _build_stats(self):
        """显示已完成的工作时段数量。"""
        self.session_label = tk.Label(
            self.root, text="Completed: 0 sessions",
            font=("Segoe UI", 9),
            fg=self.COLOR_TEXT_SECONDARY, bg=self.COLOR_BG,
        )
        self.session_label.pack(pady=8)

    def _build_settings(self):
        """构建时长设置区域：三个 Spinbox + Apply 按钮。"""
        frame = tk.Frame(self.root, bg=self.COLOR_BG)
        frame.pack(pady=4)

        # 三个设置项：标签名、属性名、默认值（分钟）
        items = [
            ("Work (min)", "work_spinbox", self.WORK // 60),
            ("Short Break (min)", "short_spinbox", self.SHORT_BREAK // 60),
            ("Long Break (min)", "long_spinbox", self.LONG_BREAK // 60),
        ]

        for i, (label, attr, default) in enumerate(items):
            # 列标题
            tk.Label(
                frame, text=label,
                font=("Segoe UI", 9),
                fg=self.COLOR_TEXT_SECONDARY, bg=self.COLOR_BG,
            ).grid(row=0, column=i, padx=8)

            # Spinbox 数字输入框（范围 1-120 分钟）
            sb = tk.Spinbox(
                frame, from_=1, to=120, width=5,
                font=("Segoe UI", 9),
                fg=self.COLOR_TEXT, bg=self.COLOR_SURFACE,
                buttonbackground=self.COLOR_SURFACE,
                relief="flat", justify="center",
            )
            sb.insert(0, str(default))
            sb.grid(row=1, column=i, padx=8, pady=(2, 0))
            sb.bind("<FocusOut>", lambda e: self.save_config())  # 焦点离开时自动保存
            setattr(self, attr, sb)  # 将控件绑定为实例属性，方便后续读写

        # Apply 按钮（用于手动触发保存）
        save_btn = tk.Button(
            frame, text="Apply",
            font=("Segoe UI", 8),
            fg=self.COLOR_TEXT, bg=self.COLOR_SURFACE,
            activeforeground=self.COLOR_TEXT,
            activebackground=self.COLOR_SURFACE_HOVER,
            relief="flat", padx=10, pady=2,
            command=self.save_config,
        )
        save_btn.grid(row=1, column=3, padx=8, pady=(2, 0))

    def _build_bottom(self):
        """构建底部"窗口置顶"复选框。"""
        self.ontop_var = tk.BooleanVar(value=False)
        cb = tk.Checkbutton(
            self.root, text="Always on top",
            variable=self.ontop_var,
            command=self.toggle_ontop,
            font=("Segoe UI", 9),
            fg=self.COLOR_TEXT_SECONDARY, bg=self.COLOR_BG,
            selectcolor=self.COLOR_SURFACE,
            activebackground=self.COLOR_BG,
            activeforeground=self.COLOR_TEXT,
        )
        cb.pack(pady=8)

    # ══════════════════════════════════════════════════════════════
    #  计时器状态机 —— 核心逻辑
    # ══════════════════════════════════════════════════════════════

    def start(self):
        """
        启动或恢复计时器。
        - IDLE → RUNNING：开始新计时
        - PAUSED → RUNNING：从暂停处恢复
        - RUNNING 状态下调用无效果
        """
        if self.state == self.RUNNING:
            return
        self.state = self.RUNNING
        self.set_controls()
        self.tick()

    def pause(self):
        """
        暂停计时器。
        - RUNNING → PAUSED：取消定时器，保留当前剩余时间
        - 非 RUNNING 状态下调用无效果（按钮本身会被禁用）
        """
        if self.state == self.RUNNING:
            self.state = self.PAUSED
            self.cancel_timer()
            self.set_controls()

    def reset(self):
        """
        重置计时器到当前模式的初始状态。
        取消定时器，恢复 remaining 为 total，回到 IDLE 状态。
        """
        self.cancel_timer()
        self.state = self.IDLE
        self.remaining = self.total
        self.update_display()
        self.set_controls()

    def tick(self):
        """
        计时器核心循环 —— 每秒执行一次。
        当 remaining > 0 时：自减 1，更新显示，然后用 root.after 安排下一秒再调用自身。
        当 remaining == 0 时：触发 on_complete 完成流程。
        仅在 RUNNING 状态下执行，否则直接返回。
        """
        if self.state != self.RUNNING:
            return

        if self.remaining <= 0:
            self.on_complete()
            return

        self.remaining -= 1
        self.update_display()
        # 安排 1000ms 后再次调用 tick，形成每秒一次的回调链
        self.after_id = self.root.after(1000, self.tick)

    def on_complete(self):
        """
        计时完成时的处理流程：
          1. 取消定时器，播放 4 声提示音
          2. 如果是工作模式结束：工作计数 +1，根据计数决定下一模式
          3. 如果是休息模式结束：下一模式固定为 work
          4. 切换到下一模式，状态归 IDLE，弹出提示对话框
        """
        self.cancel_timer()

        # 播放 4 声短促的蜂鸣
        for _ in range(4):
            winsound.Beep(1000, 150)  # 频率 1000Hz，持续 150ms

        if self.mode == "work":
            # 工作完成：计数器 +1
            self.work_sessions += 1
            self.session_label.config(
                text=f"Completed: {self.work_sessions} session{'s' if self.work_sessions != 1 else ''}"
            )
            # 每 4 个工作时段后进入长休息，否则短休息
            next_mode = "long_break" if self.work_sessions % 4 == 0 else "short_break"
        else:
            # 休息结束 → 下一轮工作
            next_mode = "work"

        # 切换到下一模式
        self._apply_mode(next_mode)

        # 将窗口提到最前并弹窗通知
        self.root.lift()
        self.root.focus_force()
        messagebox.showinfo(
            "Time's up!",
            f"Starting: {self.current_name}",
        )

    def cancel_timer(self):
        """
        取消由 root.after 注册的定时回调。
        安全操作：即使 after_id 为 None 也不会出错。
        """
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None

    # ══════════════════════════════════════════════════════════════
    #  UI 辅助方法
    # ══════════════════════════════════════════════════════════════

    def update_display(self):
        """
        更新画布上的两个元素：
          1. 数字时间标签（mm:ss 格式）
          2. 前景进度弧的扫过角度（剩余时间比例 × 360°）
        """
        mins, secs = divmod(self.remaining, 60)
        self.time_label.config(text=f"{mins:02d}:{secs:02d}")

        ratio = self.remaining / self.total if self.total > 0 else 0
        extent = 359.999 * ratio

        self.canvas.itemconfig(self.progress_ring, extent=extent, outline=self.current_color)

    def update_mode_label(self):
        """更新模式名称标签的文字和颜色。"""
        self.mode_label.config(text=self.current_name, fg=self.current_color)

    def update_mode_buttons(self):
        """
        更新模式切换按钮的样式：
        - 当前模式的按钮填充其主题色（高亮）
        - 其余按钮恢复为默认表面色
        """
        for mode, (btn, color) in self.mode_buttons.items():
            if mode == self.mode:
                btn.config(bg=color)
            else:
                btn.config(bg=self.COLOR_SURFACE)

    def set_controls(self):
        """
        根据 self.state 调整控制按钮的启用/禁用和文字。

        三种状态的表现：
          - IDLE：    Start 可用（显示"Start"），Pause 禁用，Reset 可用
          - RUNNING： Start 禁用，Pause 可用（显示"Pause"），Reset 可用
          - PAUSED：  Start 可用（显示"Resume"），Pause 禁用，Reset 可用
        """
        st = self.state
        self.start_btn.config(
            text="Start" if st != self.PAUSED else "Resume",
            state="normal" if st != self.RUNNING else "disabled",
            bg="#2E7D32" if st != self.RUNNING else "#424242",
        )
        self.pause_btn.config(
            text="Pause",
            state="normal" if st == self.RUNNING else "disabled",
            bg="#F57F17" if st == self.RUNNING else "#424242",
        )
        self.reset_btn.config(state="normal", bg="#616161")

    # ══════════════════════════════════════════════════════════════
    #  模式切换
    # ══════════════════════════════════════════════════════════════

    def _apply_mode(self, mode):
        """将计时器切换到指定模式，重置为 IDLE 状态并刷新全部 UI。"""
        self.mode = mode
        self.state = self.IDLE
        self.total = self._durations[mode]
        self.remaining = self.total
        self.update_display()
        self.update_mode_label()
        self.update_mode_buttons()
        self.set_controls()

    def switch_mode(self, mode):
        """
        切换到指定的计时模式。
        - 如果计时器正在运行，弹出确认对话框（切换会导致重置）
        - 切换后状态归 IDLE，使用新模式的时长
        """
        if self.state == self.RUNNING:
            if not messagebox.askyesno(
                "Switch Mode",
                "Timer is running. Switch mode and reset?",
            ):
                return
            self.cancel_timer()

        self._apply_mode(mode)

    # ══════════════════════════════════════════════════════════════
    #  属性（property） —— 便捷获取模式相关信息
    # ══════════════════════════════════════════════════════════════

    @property
    def _durations(self):
        """当前各模式的时长映射（秒），随用户配置动态变化。"""
        return {
            "work": self.WORK,
            "short_break": self.SHORT_BREAK,
            "long_break": self.LONG_BREAK,
        }

    @property
    def current_color(self):
        """根据当前 mode 返回对应的主题色。"""
        return getattr(self, self.META[self.mode][1])

    @property
    def current_name(self):
        """根据当前 mode 返回对应的显示名称。"""
        return self.META[self.mode][0]

    # ══════════════════════════════════════════════════════════════
    #  配置持久化
    # ══════════════════════════════════════════════════════════════

    def load_config(self):
        """
        从 ~/.pomodoro_config.json 加载用户自定义时长配置。
        如果文件不存在或格式错误，使用默认值并返回空字典。
        加载成功后直接更新类属性 WORK / SHORT_BREAK / LONG_BREAK。
        """
        try:
            if self.config_path.exists():
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                # 将读取的分钟数转换为秒，更新类级默认值
                self.WORK = int(data.get("work", 25)) * 60
                self.SHORT_BREAK = int(data.get("short_break", 5)) * 60
                self.LONG_BREAK = int(data.get("long_break", 15)) * 60
                return data
        except Exception:
            pass  # 任何异常都静默处理，使用默认值
        return {}

    def save_config(self):
        """
        将 Spinbox 中的时长值保存到 JSON 文件。
        同时更新类属性，以便新建计时器使用最新值。
        如果当前处于 IDLE 状态，立即刷新显示的剩余时间。
        """
        try:
            data = {
                "work": int(self.work_spinbox.get()),
                "short_break": int(self.short_spinbox.get()),
                "long_break": int(self.long_spinbox.get()),
            }
            self.config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            # 更新类属性（分钟转秒）
            self.WORK = data["work"] * 60
            self.SHORT_BREAK = data["short_break"] * 60
            self.LONG_BREAK = data["long_break"] * 60

            # 空闲状态下立即刷新显示
            if self.state == self.IDLE:
                self.total = self._durations[self.mode]
                self.remaining = self.total
                self.update_display()
        except Exception:
            pass  # 静默处理保存异常

    def apply_config(self):
        """
        将已加载的配置值写入 Spinbox 控件。
        在应用启动时调用，确保 UI 显示与实际值一致。
        """
        for key, attr in [("work", "work_spinbox"), ("short_break", "short_spinbox"), ("long_break", "long_spinbox")]:
            if key in self.config:
                sb = getattr(self, attr)
                sb.delete(0, "end")
                sb.insert(0, str(int(self.config[key])))

        self.total = self.WORK
        self.remaining = self.total
        self.update_display()

    # ══════════════════════════════════════════════════════════════
    #  其他
    # ══════════════════════════════════════════════════════════════

    def toggle_ontop(self):
        """切换窗口置顶属性。"""
        self.root.wm_attributes("-topmost", self.ontop_var.get())

    def on_closing(self):
        """窗口关闭回调：保存配置后销毁窗口。"""
        self.save_config()
        self.root.destroy()


# ── 程序入口 ──────────────────────────────────────────────────────
if __name__ == "__main__":
    PomodoroApp()
