import tkinter as tk
from tkinter import ttk, scrolledtext, font, messagebox, colorchooser
import os
import re
import json
from datetime import datetime


class NovelReader:
    def __init__(self, root, db, book_id, file_path):
        """
        初始化小说阅读器

        参数:
        root - Tkinter根窗口或Toplevel窗口
        db - 数据库对象
        book_id - 书籍ID
        file_path - 小说文件路径
        """
        self.root = root
        self.db = db
        self.book_id = book_id
        self.file_path = file_path
        self.book_info = db.get_book(book_id)

        # 设置窗口标题
        if self.book_info:
            root.title(f"阅读: {self.book_info['title']} - {self.book_info['author']}")
        else:
            root.title("小说阅读器")

        # 加载阅读进度
        self.load_reading_progress()

        # 创建界面
        self.create_widgets()

        # 加载小说内容
        self.load_novel_content()

        # 设置窗口关闭事件
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 跟踪阅读时间
        self.reading_start_time = datetime.now()
        self.root.after(60000, self.update_reading_time)  # 每分钟更新一次阅读时间

        # 夜间模式标志
        self.night_mode = False

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

        # 目录按钮
        ttk.Button(nav_frame, text="目录", command=self.show_chapter_list).pack(side=tk.LEFT, padx=5)

        # 进度显示
        progress_frame = ttk.Frame(toolbar)
        progress_frame.pack(side=tk.LEFT, padx=20)

        ttk.Label(progress_frame, text="进度:").pack(side=tk.LEFT)
        self.progress_var = tk.StringVar()
        ttk.Label(progress_frame, textvariable=self.progress_var).pack(side=tk.LEFT)

        # 右侧按钮组
        btn_frame = ttk.Frame(toolbar)
        btn_frame.pack(side=tk.RIGHT)

        # 书签按钮
        self.bookmark_btn = ttk.Button(btn_frame, text="添加书签", command=self.toggle_bookmark)
        self.bookmark_btn.pack(side=tk.LEFT, padx=5)

        # 夜间模式按钮
        self.night_mode_btn = ttk.Button(btn_frame, text="夜间模式", command=self.toggle_night_mode)
        self.night_mode_btn.pack(side=tk.LEFT, padx=5)

        # 设置按钮
        settings_btn = ttk.Button(btn_frame, text="设置", command=self.open_settings)
        settings_btn.pack(side=tk.LEFT, padx=5)

        # 文本显示区域
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        # 创建带滚动条的文本区域
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

        # 绑定滚动事件以更新位置
        self.text_area.bind("<MouseWheel>", self.update_position)
        self.text_area.bind("<Button-4>", self.update_position)  # Linux向上滚动
        self.text_area.bind("<Button-5>", self.update_position)  # Linux向下滚动
        self.text_area.bind("<Key>", self.update_position)  # 键盘导航

    def load_reading_progress(self):
        """从数据库加载阅读进度"""
        self.reading_progress = self.db.get_reading_progress(self.book_id)

        if not self.reading_progress:
            # 初始化默认进度
            self.reading_progress = {
                'current_chapter': 1,
                'chapter_position': 0,
                'last_read_time': datetime.now(),
                'bookmarked': False,
                'notes': '',
                'start_chapter': 1
            }

        # 更新书签按钮状态
        self.update_bookmark_button()

    def load_novel_content(self):
        """加载小说内容"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.full_content = f.read()

            # 解析章节
            self.parse_chapters()

            # 显示当前章节
            self.show_current_chapter()

        except Exception as e:
            messagebox.showerror("错误", f"无法加载小说文件: {str(e)}")
            self.root.destroy()

    def parse_chapters(self):
        """解析小说章节"""
        # 使用正则表达式匹配章节标题
        # 支持多种章节格式：第X章、第X节、Chapter X等
        chapter_pattern = r'(第[零一二三四五六七八九十百千\d]+章|第[零一二三四五六七八九十百千\d]+节|Chapter\s+\d+|卷[零一二三四五六七八九十百千\d]+)\s+(.*?)\n'

        self.chapters = []
        matches = re.finditer(chapter_pattern, self.full_content)

        last_end = 0
        for match in matches:
            start, end = match.span()
            title = match.group(0).strip()

            # 添加上一章节的内容
            if start > last_end:
                chapter_content = self.full_content[last_end:start]
                self.chapters.append({
                    'title': f"第{len(self.chapters) + 1}章",
                    'content': chapter_content
                })

            # 添加当前章节
            self.chapters.append({
                'title': title,
                'content': self.full_content[start:end]
            })
            last_end = end

        # 添加最后一章
        if last_end < len(self.full_content):
            chapter_content = self.full_content[last_end:]
            self.chapters.append({
                'title': f"第{len(self.chapters) + 1}章",
                'content': chapter_content
            })

        # 如果没有找到章节，将整个内容作为一章
        if not self.chapters:
            self.chapters.append({
                'title': "全文",
                'content': self.full_content
            })

    def show_current_chapter(self):
        """显示当前章节内容"""
        chapter_index = self.reading_progress['current_chapter'] - 1

        if chapter_index < 0:
            chapter_index = 0
        if chapter_index >= len(self.chapters):
            chapter_index = len(self.chapters) - 1

        chapter = self.chapters[chapter_index]

        # 更新文本区域
        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete(1.0, tk.END)

        # 添加章节标题（大号字体）
        self.text_area.tag_configure("title", font=("宋体", 16, "bold"))
        self.text_area.insert(tk.END, f"{chapter['title']}\n\n", "title")

        # 添加章节内容
        self.text_area.insert(tk.END, chapter['content'])
        self.text_area.config(state=tk.DISABLED)

        # 滚动到保存的位置
        position = self.reading_progress['chapter_position']
        if position > 0:
            self.text_area.yview_moveto(position)

        # 更新进度显示
        self.update_progress_display()

    def update_progress_display(self):
        """更新进度显示"""
        current = self.reading_progress['current_chapter']
        total = len(self.chapters)
        percentage = int((current / total) * 100)
        self.progress_var.set(f"{current}/{total}章 ({percentage}%)")

    def prev_chapter(self):
        """跳转到上一章"""
        if self.reading_progress['current_chapter'] > 1:
            self.save_current_position()
            self.reading_progress['current_chapter'] -= 1
            self.reading_progress['chapter_position'] = 0
            self.show_current_chapter()

    def next_chapter(self):
        """跳转到下一章"""
        if self.reading_progress['current_chapter'] < len(self.chapters):
            self.save_current_position()
            self.reading_progress['current_chapter'] += 1
            self.reading_progress['chapter_position'] = 0
            self.show_current_chapter()

    def show_chapter_list(self):
        """显示章节列表"""
        chapter_dialog = tk.Toplevel(self.root)
        chapter_dialog.title("章节列表")
        chapter_dialog.geometry("400x500")

        # 创建章节列表
        tree = ttk.Treeview(chapter_dialog, columns=("title"), show="tree")
        tree.column("#0", width=0, stretch=tk.NO)  # 隐藏第一列

        for i, chapter in enumerate(self.chapters, 1):
            tree.insert("", "end", iid=i, values=(chapter['title'],))

        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 跳转到当前章节
        current_chapter = self.reading_progress['current_chapter']
        if 1 <= current_chapter <= len(self.chapters):
            tree.selection_set(current_chapter)
            tree.see(current_chapter)

        def jump_to_chapter():
            selected = tree.selection()
            if not selected:
                return

            chapter_index = int(selected[0])
            self.reading_progress['current_chapter'] = chapter_index
            self.reading_progress['chapter_position'] = 0
            self.show_current_chapter()
            chapter_dialog.destroy()

        btn_frame = ttk.Frame(chapter_dialog)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="跳转", command=jump_to_chapter).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=chapter_dialog.destroy).pack(side=tk.LEFT, padx=5)

    def update_position(self, event=None):
        """更新阅读位置"""
        # 获取当前滚动位置（0.0到1.0）
        position = self.text_area.yview()[0]
        self.reading_progress['chapter_position'] = position

        # 自动保存位置（每30秒一次）
        if not hasattr(self, 'last_save_time') or (datetime.now() - self.last_save_time).seconds > 30:
            self.save_current_position()

    def save_current_position(self):
        """保存当前阅读位置"""
        self.db.save_reading_progress(
            self.book_id,
            self.reading_progress['current_chapter'],
            self.reading_progress['chapter_position'],
            self.reading_progress['notes']
        )
        self.last_save_time = datetime.now()

    def toggle_bookmark(self):
        """切换书签状态"""
        self.reading_progress['bookmarked'] = not self.reading_progress['bookmarked']
        self.db.toggle_bookmark(self.book_id)
        self.update_bookmark_button()

        # 显示提示信息
        if self.reading_progress['bookmarked']:
            messagebox.showinfo("书签", "已添加书签")
        else:
            messagebox.showinfo("书签", "已移除书签")

    def update_bookmark_button(self):
        """更新书签按钮状态"""
        if self.reading_progress.get('bookmarked', False):
            self.bookmark_btn.config(text="移除书签")
        else:
            self.bookmark_btn.config(text="添加书签")

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

    def update_reading_time(self):
        """更新阅读时间记录"""
        now = datetime.now()
        duration = (now - self.reading_start_time).seconds

        # 如果阅读时间超过1分钟，保存阅读历史
        if duration > 60:
            # 计算阅读的章节数
            current_chapter = self.reading_progress['current_chapter']
            start_chapter = self.reading_progress.get('start_chapter', current_chapter)
            chapters_read = current_chapter - start_chapter + 1

            # 保存阅读历史
            self.db.add_reading_history(self.book_id, duration, chapters_read)

            # 重置计时
            self.reading_start_time = now
            self.reading_progress['start_chapter'] = current_chapter

        # 每分钟检查一次
        self.root.after(60000, self.update_reading_time)

    def on_close(self):
        """窗口关闭时的处理"""
        # 保存当前阅读进度
        self.save_current_position()

        # 记录阅读时间
        self.update_reading_time()

        # 关闭窗口
        self.root.destroy()