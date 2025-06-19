import tkinter as tk
from tkinter import ttk, scrolledtext, font, messagebox, colorchooser
import os
import re
import json
import threading
import chardet
from datetime import datetime

class NovelReader:
    def __init__(self, root, db, book_id, file_path):
        self.root = root
        self.db = db
        self.book_id = book_id
        self.file_path = file_path
        self.book_info = db.get_book(book_id)

        # 初始化所有属性
        self.chapters = []  # 章节列表
        self.current_chapter_index = 0  # 当前章节索引
        self.bookmarked = False  # 收藏状态
        self.reading_progress = None  # 阅读进度
        self.reading_start_time = datetime.now()  # 开始阅读时间
        self.night_mode = False  # 夜间模式
        self.notes_text = None  # 笔记文本框
        self.chapter_positions = {}  # 章节起始位置标记

        # 设置窗口标题
        if self.book_info:
            root.title(f"阅读: {self.book_info['title']} - {self.book_info['author']}")
        else:
            root.title("小说阅读器")

        # 确保 text_area 被正确引用
        self.text_area = None

        # 创建界面
        self.create_widgets()

        # 加载阅读进度
        self.load_reading_progress()

        # 解析小说内容
        self.chapters = self.parse_novel_content()

        # 一次性加载所有章节
        if self.chapters:
            self.display_all_chapters()
        else:
            messagebox.showerror("错误", "无法加载小说内容")

        # 设置窗口关闭事件
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        """创建阅读器界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 顶部工具栏
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        # 导航按钮
        nav_frame = ttk.Frame(toolbar)
        nav_frame.pack(side=tk.LEFT)

        self.prev_btn = ttk.Button(nav_frame, text="上一章", command=self.prev_chapter)
        self.prev_btn.pack(side=tk.LEFT, padx=5)

        self.next_btn = ttk.Button(nav_frame, text="下一章", command=self.next_chapter)
        self.next_btn.pack(side=tk.LEFT, padx=5)

        # 章节跳转按钮（功能暂不可用）
        self.chapter_jump_btn = ttk.Button(toolbar, text="章节跳转(暂不可用)", command=self.show_chapter_list)
        self.chapter_jump_btn.pack(side=tk.LEFT, padx=5)
        self.chapter_jump_btn.config(state=tk.DISABLED)

        # 进度显示
        progress_frame = ttk.Frame(toolbar)
        progress_frame.pack(side=tk.LEFT, padx=20)

        ttk.Label(progress_frame, text="进度:").pack(side=tk.LEFT)
        self.progress_var = tk.StringVar()
        ttk.Label(progress_frame, textvariable=self.progress_var).pack(side=tk.LEFT)

        # 右侧按钮组
        btn_frame = ttk.Frame(toolbar)
        btn_frame.pack(side=tk.RIGHT)

        # 收藏按钮
        self.bookmark_btn = ttk.Button(btn_frame, text="收藏", command=self.toggle_bookmark)
        self.bookmark_btn.pack(side=tk.LEFT, padx=5)
        # 启用收藏按钮
        self.bookmark_btn.config(state=tk.NORMAL)

        # 夜间模式按钮
        self.night_mode_btn = ttk.Button(btn_frame, text="夜间模式", command=self.toggle_night_mode)
        self.night_mode_btn.pack(side=tk.LEFT, padx=5)

        # 设置按钮
        settings_btn = ttk.Button(btn_frame, text="设置", command=self.open_settings)
        settings_btn.pack(side=tk.LEFT, padx=5)

        # 文本显示区域
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        chapter_frame = ttk.Frame(self.root)
        chapter_frame.pack(fill=tk.X, padx=10, pady=5)

        self.prev_btn = ttk.Button(chapter_frame, text="上一章", command=self.prev_chapter)
        self.prev_btn.pack(side=tk.LEFT)

        self.chapter_label = ttk.Label(chapter_frame, text="章节: 1/1")
        self.chapter_label.pack(side=tk.LEFT, expand=True)

        self.next_btn = ttk.Button(chapter_frame, text="下一章", command=self.next_chapter)
        self.next_btn.pack(side=tk.RIGHT)

        self.text_area = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            font=("宋体", 14),
            padx=20,
            pady=20,
            bg="#F8F8F8",
            fg="#333333",
            spacing1=5,  # 行间距
            spacing3=5
        )
        self.text_area.pack(fill=tk.BOTH, expand=True)
        self.text_area.config(state=tk.DISABLED)

        # 只保留滚动事件绑定，删除键盘导航绑定
        self.text_area.bind("<MouseWheel>", self.on_scroll)
        self.text_area.bind("<Button-4>", self.on_scroll)  # Linux向上滚动
        self.text_area.bind("<Button-5>", self.on_scroll)  # Linux向下滚动

    def display_all_chapters(self):
        """一次性显示所有章节"""
        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete(1.0, tk.END)

        # 清空章节位置标记
        self.chapter_positions = {}

        # 添加所有章节内容
        for idx, chapter in enumerate(self.chapters):
            # 标记章节起始位置
            self.chapter_positions[idx] = self.text_area.index(tk.END)

            # 添加章节标题
            self.text_area.insert(tk.END, f"{chapter['title']}\n\n", "title")
            # 添加章节内容
            self.text_area.insert(tk.END, chapter['content'] + "\n\n")

        self.text_area.config(state=tk.DISABLED)

        # 更新章节标签
        self.chapter_label.config(text=f"章节: {self.current_chapter_index + 1}/{len(self.chapters)}")

        # 滚动到当前章节位置
        if self.current_chapter_index in self.chapter_positions:
            self.text_area.see(self.chapter_positions[self.current_chapter_index])
            self.text_area.yview_moveto(
                self.reading_progress.get('chapter_position', 0)
            )

    def load_reading_progress(self):
        """从数据库加载阅读进度"""
        self.reading_progress = self.db.get_reading_progress(self.book_id)

        if self.reading_progress:
            # 从数据库加载收藏状态
            self.bookmarked = bool(self.reading_progress.get('bookmarked', False))
            # 设置当前章节索引
            self.current_chapter_index = self.reading_progress.get('current_chapter', 1) - 1
        else:
            # 初始化默认进度
            self.reading_progress = {
                'current_chapter': 1,
                'chapter_position': 0,
                'last_read_time': datetime.now(),
                'bookmarked': False,
                'notes': '',
                'start_chapter': 1
            }
            self.bookmarked = False
            self.current_chapter_index = 0

    def parse_novel_content(self):
        """解析小说内容为章节列表 - 简化实现"""
        chapters = []

        if not os.path.exists(self.file_path):
            messagebox.showerror("错误", f"文件不存在: {self.file_path}")
            return chapters

        try:
            # 检测文件编码
            with open(self.file_path, 'rb') as f:
                raw_data = f.read(4096)
                encoding = chardet.detect(raw_data)['encoding'] or 'utf-8'

            # 读取文件内容
            with open(self.file_path, 'r', encoding=encoding, errors='replace') as f:
                content = f.read()

            # 常见章节标题模式
            patterns = [
                r'第[一二三四五六七八九十百千万零\d]+章\s+[^\n]+',  # 第X章 标题
                r'第[一二三四五六七八九十百千万零\d]+节\s+[^\n]+',  # 第X节 标题
                r'[卷卷]\s*[一二三四五六七八九十百千万零\d]+\s+[^\n]+',  # 卷X 标题
                r'^\s*[一二三四五六七八九十百千万零\d]+\s+[^\n]+',  # 数字标题
                r'^\s*[^\n]{3,20}\n[=-]{10,}',  # 标题下划线
            ]

            # 尝试匹配章节
            last_end = 0
            for pattern in patterns:
                matches = list(re.finditer(pattern, content, re.MULTILINE))
                if matches:
                    for i, match in enumerate(matches):
                        start = match.start()
                        title = match.group().strip()

                        # 添加章节内容
                        if i == 0 and start > 0:
                            # 添加开头的非章节内容
                            chapters.append({
                                "title": "前言",
                                "content": content[0:start]
                            })

                        # 确定章节结束位置
                        next_start = matches[i + 1].start() if i + 1 < len(matches) else len(content)
                        chapter_content = content[start:next_start]

                        chapters.append({
                            "title": title,
                            "content": chapter_content
                        })
                    break
            else:
                # 没有找到章节标题，整个内容作为一章
                chapters.append({
                    "title": "全文",
                    "content": content
                })

            return chapters
        except Exception as e:
            messagebox.showerror("解析错误", f"解析小说内容失败: {e}")
            return [{"title": "错误", "content": f"无法解析小说内容: {str(e)}"}]

    def toggle_night_mode(self):
        """切换夜间模式"""
        if self.night_mode:
            # 切换到日间模式
            self.text_area.config(bg="#F8F8F8", fg="#333333")
            self.night_mode = False
            self.night_mode_btn.config(text="夜间模式")
        else:
            # 切换到夜间模式
            self.text_area.config(bg="#1E1E1E", fg="#E0E0E0")
            self.night_mode = True
            self.night_mode_btn.config(text="日间模式")

    def open_settings(self):
        """打开阅读设置对话框"""
        settings_dialog = tk.Toplevel(self.root)
        settings_dialog.title("阅读设置")
        settings_dialog.transient(self.root)
        settings_dialog.grab_set()

        # 字体设置
        font_frame = ttk.LabelFrame(settings_dialog, text="字体设置")
        font_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(font_frame, text="字体:").grid(row=0, column=0, padx=5, pady=5)
        self.font_family = tk.StringVar(value=self.text_area.cget("font").split()[0])
        font_families = list(font.families())
        font_families.sort()

        font_combo = ttk.Combobox(font_frame, textvariable=self.font_family, values=font_families)
        font_combo.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(font_frame, text="大小:").grid(row=0, column=2, padx=5, pady=5)
        self.font_size = tk.IntVar(value=int(self.text_area.cget("font").split()[1]))
        size_spin = ttk.Spinbox(font_frame, from_=8, to=36, textvariable=self.font_size, width=5)
        size_spin.grid(row=0, column=3, padx=5, pady=5)

        # 颜色设置
        color_frame = ttk.LabelFrame(settings_dialog, text="颜色设置")
        color_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(color_frame, text="背景:").grid(row=0, column=0, padx=5, pady=5)
        self.bg_color = tk.StringVar(value=self.text_area.cget("bg"))
        bg_entry = ttk.Entry(color_frame, textvariable=self.bg_color, width=10)
        bg_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(color_frame, text="选择", command=lambda: self.choose_color(self.bg_color)).grid(row=0, column=2,
                                                                                                    padx=5, pady=5)

        ttk.Label(color_frame, text="文字:").grid(row=1, column=0, padx=5, pady=5)
        self.fg_color = tk.StringVar(value=self.text_area.cget("fg"))
        fg_entry = ttk.Entry(color_frame, textvariable=self.fg_color, width=10)
        fg_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(color_frame, text="选择", command=lambda: self.choose_color(self.fg_color)).grid(row=1, column=2,
                                                                                                    padx=5, pady=5)

        # 行距设置
        spacing_frame = ttk.LabelFrame(settings_dialog, text="行距设置")
        spacing_frame.pack(fill=tk.X, padx=10, pady=10)

        self.line_spacing = tk.IntVar(value=5)
        ttk.Scale(
            spacing_frame,
            from_=0,
            to=20,
            variable=self.line_spacing,
            orient=tk.HORIZONTAL,
            command=lambda v: self.apply_line_spacing()
        ).pack(fill=tk.X, padx=10, pady=10)

        # 应用按钮
        btn_frame = ttk.Frame(settings_dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text="应用", command=self.apply_settings).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=settings_dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # 初始化设置
        self.apply_settings()

    def choose_color(self, color_var):
        """选择颜色"""
        color = colorchooser.askcolor(title="选择颜色", initialcolor=color_var.get())
        if color[1]:
            color_var.set(color[1])

    def apply_settings(self):
        """应用阅读设置"""
        # 更新字体
        font_spec = (self.font_family.get(), self.font_size.get())
        self.text_area.config(font=font_spec)

        # 更新颜色
        self.text_area.config(bg=self.bg_color.get(), fg=self.fg_color.get())

        # 应用行距
        self.apply_line_spacing()

    def apply_line_spacing(self, event=None):
        """应用行间距设置"""
        spacing = self.line_spacing.get()
        self.text_area.config(spacing1=spacing, spacing2=spacing, spacing3=spacing)

    def on_close(self):
        """窗口关闭事件处理"""
        # 保存当前位置 - 使用同步方式确保在关闭前保存
        if hasattr(self, 'chapters') and self.chapters:
            # 安全获取当前章节索引
            current_chapter_index = getattr(self, 'current_chapter_index', 0)
            current_chapter = current_chapter_index + 1

            # 安全获取滚动位置
            position = 0.0
            try:
                position = self.text_area.yview()[0]
            except:
                pass

            # 安全获取收藏状态
            bookmarked = getattr(self, 'bookmarked', False)

            # 安全获取笔记内容
            notes = ""
            if hasattr(self, 'notes_text'):
                try:
                    notes = self.notes_text.get("1.0", tk.END).strip()
                except:
                    pass

            # 保存进度
            self.db.save_reading_progress(
                self.book_id,
                current_chapter,
                position,
                bookmarked,
                notes
            )

        # 关闭窗口
        self.root.destroy()

    def on_scroll(self, event):
        """处理滚动事件，只更新当前章节索引"""
        # 更新当前章节索引
        self.update_current_chapter_index()

    def update_current_chapter_index(self):
        """根据可见内容确定当前章节索引"""
        visible_start = self.text_area.yview()[0]
        for idx, pos in sorted(self.chapter_positions.items(), reverse=True):
            if float(pos) <= visible_start:
                self.current_chapter_index = idx
                self.chapter_label.config(text=f"章节: {self.current_chapter_index + 1}/{len(self.chapters)}")
                break

    def next_chapter(self):
        """跳转到下一章开头位置"""
        if self.current_chapter_index < len(self.chapters) - 1:
            # 更新当前章节索引
            self.current_chapter_index += 1

            # 跳转到下一章开头位置
            if self.current_chapter_index in self.chapter_positions:
                self.text_area.see(self.chapter_positions[self.current_chapter_index])

            # 更新章节标签
            self.chapter_label.config(text=f"章节: {self.current_chapter_index + 1}/{len(self.chapters)}")

            # 保存位置
            self.save_current_position()

    def prev_chapter(self):
        """跳转到上一章开头位置"""
        if self.current_chapter_index > 0:
            # 更新当前章节索引
            self.current_chapter_index -= 1

            # 跳转到上一章开头位置
            if self.current_chapter_index in self.chapter_positions:
                self.text_area.see(self.chapter_positions[self.current_chapter_index])

            # 更新章节标签
            self.chapter_label.config(text=f"章节: {self.current_chapter_index + 1}/{len(self.chapters)}")

            # 保存位置
            self.save_current_position()

    def save_current_position(self):
        """保存当前阅读位置"""
        # 获取当前滚动位置
        position = self.text_area.yview()[0]

        # 保存到数据库
        threading.Thread(
            target=self.db.save_reading_progress,
            args=(
                self.book_id,
                self.current_chapter_index + 1,  # 1-based索引
                position
            ),
            daemon=True
        ).start()

    def toggle_bookmark(self):
        """切换收藏状态"""
        self.bookmarked = not self.bookmarked
        # 更新按钮文本
        self.bookmark_btn.config(text="取消收藏" if self.bookmarked else "收藏")
        # 保存收藏状态
        self.db.toggle_bookmark(self.book_id)
        # 显示提示信息
        status = "已收藏" if self.bookmarked else "已取消收藏"
        messagebox.showinfo("提示", f"{self.book_info['title']} {status}")

#架空
    def show_chapter_list(self):
        """章节跳转功能（暂不可用）"""
        pass
