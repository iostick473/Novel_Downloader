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
        self.chapter_positions = {}  # 章节起始位置标记
        self.total_lines = 0
        self.last_progress_update = datetime.now()

        # 设置窗口标题
        if self.book_info:
            root.title(f"阅读: {self.book_info['title']} - {self.book_info['author']}")
        else:
            root.title("小说阅读器")

        # 确保 text_area 被正确引用
        self.text_area = None

        # 加载阅读进度
        self.load_reading_progress()

        # 创建界面
        self.create_widgets()

        # 解析小说内容
        self.chapters = self.parse_novel_content()

        # 一次性加载所有章节
        if self.chapters:
            self.display_all_chapters()
        else:
            messagebox.showerror("错误", "无法加载小说内容", parent=self.root)

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

        # 章节跳转按钮
        self.chapter_jump_btn = ttk.Button(toolbar, text="章节跳转", command=self.show_chapter_list)
        self.chapter_jump_btn.pack(side=tk.LEFT, padx=5)
        self.chapter_jump_btn.config(state=tk.NORMAL)

        # 进度显示
        progress_frame = ttk.Frame(toolbar)
        progress_frame.pack(side=tk.LEFT, padx=20)

        ttk.Label(progress_frame, text="进度:").pack(side=tk.LEFT)
        self.progress_var = tk.StringVar()
        self.progress_var.set("0/0")  # 初始化为0/0
        ttk.Label(progress_frame, textvariable=self.progress_var).pack(side=tk.LEFT)

        # 右侧按钮组
        btn_frame = ttk.Frame(toolbar)
        btn_frame.pack(side=tk.RIGHT)

        # 收藏按钮 - 根据收藏状态初始化文本
        bookmark_text = "取消收藏" if self.bookmarked else "收藏"
        self.bookmark_btn = ttk.Button(btn_frame, text=bookmark_text, command=self.toggle_bookmark)
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

        # 滚动事件绑定，
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

        self.total_lines = float(self.text_area.index('end-1c').split('.')[0])

        # 更新章节标签
        self.chapter_label.config(text=f"章节: {self.current_chapter_index + 1}/{len(self.chapters)}")

        self.update_progress_display()

        # 滚动到当前章节位置
        if self.current_chapter_index in self.chapter_positions:
            # 计算章节位置的相对偏移量 (0.0-1.0)
            pos = self.chapter_positions[self.current_chapter_index]
            line_num = float(pos.split('.')[0])
            rel_pos = line_num / self.total_lines
            self.text_area.yview_moveto(rel_pos)

            # 如果存在保存的进度，覆盖章节位置
        if self.reading_progress.get('chapter_position', 0) > 0:
            self.text_area.yview_moveto(
                self.reading_progress.get('chapter_position', 0)
            )

    def update_progress_display(self):
        """更新进度显示为章节数（包括第0章）"""
        if not self.chapters:
            return

        # 计算当前章节和总章节数（前言作为第0章）
        current_chapter = self.current_chapter_index
        total_chapters = len(self.chapters)

        # 更新显示
        self.progress_var.set(f"{current_chapter}/{total_chapters}")

        # 每5秒自动保存一次进度
        if (datetime.now() - self.last_progress_update).seconds >= 5:
            self.save_current_position()
            self.last_progress_update = datetime.now()

    def load_reading_progress(self):
        """从数据库加载阅读进度 """
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
                'bookmarked': False
            }
            self.bookmarked = False
            self.current_chapter_index = 0

    def parse_novel_content(self):
        """解析小说内容为章节列表 - 简化实现"""
        chapters = []

        if not os.path.exists(self.file_path):
            messagebox.showerror("错误", f"文件不存在: {self.file_path}", parent=self.root)
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
                        # 从内容中移除标题行
                        content_start = match.end()
                        chapter_content = content[content_start:next_start].lstrip()

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
            messagebox.showerror("解析错误", f"解析小说内容失败: {e}", parent=self.root)
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
            # 保存当前阅读位置
            self.save_current_position(sync=True)

            # 关闭窗口
        self.root.destroy()

    def on_scroll(self, event=None):
        """处理滚动事件，更新当前章节索引并记录位置"""
        # 更新当前章节索引
        self.update_current_chapter_index()

        # 更新进度显示
        self.update_progress_display()

        # 记录当前位置
        self.save_current_position()

    def update_current_chapter_index(self):
        """根据可见内容确定当前章节索引"""
        # 获取当前可见区域的起始位置（0.0-1.0）
        visible_start = self.text_area.yview()[0]

        # 将章节位置转换为可比较的浮点数
        chapter_positions = {}
        for idx, text_index in self.chapter_positions.items():
            # 将文本索引转换为相对位置（0.0-1.0）
            rel_pos = float(self.text_area.index(text_index).split('.')[0]) / float(
                self.text_area.index('end-1c').split('.')[0])
            chapter_positions[idx] = rel_pos

        # 找到当前可见区域所属的章节
        current_idx = 0
        for idx in sorted(chapter_positions.keys()):
            if chapter_positions[idx] <= visible_start:
                current_idx = idx
            else:
                break

        if self.current_chapter_index == 0:
            chapter_text = "前言"
        else:
            chapter_text = f"第{self.current_chapter_index}章"

        # 更新当前章节索引
        if self.current_chapter_index != current_idx:
            self.current_chapter_index = current_idx
            self.chapter_label.config(text=f"{chapter_text} ({self.current_chapter_index}/{len(self.chapters)})")

    def next_chapter(self):
        """跳转到下一章开头位置"""
        if self.current_chapter_index < len(self.chapters) - 1:
            # 更新当前章节索引
            self.current_chapter_index += 1

            # 跳转到下一章开头位置（显示在顶部）
            if self.current_chapter_index in self.chapter_positions:
                # 计算章节位置的相对偏移量 (0.0-1.0)
                pos = self.chapter_positions[self.current_chapter_index]
                line_num = float(pos.split('.')[0])
                rel_pos = line_num / self.total_lines
                self.text_area.yview_moveto(rel_pos)

            # 保存位置
            self.save_current_position()

            # 更新进度显示
            self.update_progress_display()

            # 更新章节标签
            self.update_current_chapter_index()

    def prev_chapter(self):
        """跳转到上一章开头位置"""
        if self.current_chapter_index > 0:
            # 更新当前章节索引
            self.current_chapter_index -= 1

            # 跳转到上一章开头位置（显示在顶部）
            if self.current_chapter_index in self.chapter_positions:
                # 计算章节位置的相对偏移量 (0.0-1.0)
                pos = self.chapter_positions[self.current_chapter_index]
                line_num = float(pos.split('.')[0])
                rel_pos = line_num / self.total_lines
                self.text_area.yview_moveto(rel_pos)

            # 保存位置
            self.save_current_position()

            # 更新进度显示
            self.update_progress_display()

            # 更新章节标签
            self.update_current_chapter_index()

    def save_current_position(self, sync=False):
        """保存当前阅读位置（包括章节推断）"""
        # 获取当前滚动位置
        position = self.text_area.yview()[0]

        # 根据位置推断当前章节
        self.update_current_chapter_index()

        # 保存到数据库
        if sync:
            # 同步保存
            self.db.save_reading_progress(
                self.book_id,
                self.current_chapter_index,  # 1-based索引
                position,
                self.bookmarked
            )
        else:
            # 异步保存
            threading.Thread(
                target=self.db.save_reading_progress,
                args=(
                    self.book_id,
                    self.current_chapter_index,
                    position,
                    self.bookmarked
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
        messagebox.showinfo("提示", f"{self.book_info['title']} {status}", parent=self.root)

    def show_chapter_list(self):
        """显示章节列表对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("章节列表")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("500x400")

        # 创建搜索框
        search_frame = ttk.Frame(dialog)
        search_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(search_frame, text="搜索章节:").pack(side=tk.LEFT, padx=5)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # 章节列表
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 创建带滚动条的列表框
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        chapter_list = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            font=("宋体", 12),
            selectbackground="#4A6984",
            selectforeground="white"
        )
        chapter_list.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=chapter_list.yview)

        for idx, chapter in enumerate(self.chapters):
            # 直接使用章节标题，不再添加额外章节信息
            display_text = f"{idx}. {chapter['title']}"
            chapter_list.insert(tk.END, display_text)

        # 设置当前选中章节
        if 0 <= self.current_chapter_index < chapter_list.size():
            chapter_list.selection_set(self.current_chapter_index)
            chapter_list.see(self.current_chapter_index)

        # 按钮区域
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        # 跳转按钮
        def jump_to_selected():
            selected = chapter_list.curselection()
            if selected:
                chapter_index = selected[0]
                self.jump_to_chapter(chapter_index)
                dialog.destroy()

        jump_btn = ttk.Button(btn_frame, text="跳转到章节", command=jump_to_selected)
        jump_btn.pack(side=tk.RIGHT, padx=5)

        # 取消按钮
        cancel_btn = ttk.Button(btn_frame, text="取消", command=dialog.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=5)

        # 搜索功能
        def filter_chapters(*args):
            search_term = search_var.get().lower()
            chapter_list.delete(0, tk.END)

            for idx, chapter in enumerate(self.chapters):
                if search_term in chapter['title'].lower():
                    chapter_list.insert(tk.END, f"{idx + 1}. {chapter['title']}")

        search_var.trace("w", filter_chapters)

        # 双击跳转
        def on_double_click(event):
            jump_to_selected()

    def jump_to_chapter(self, chapter_index):
        """跳转到指定章节"""
        if 0 <= chapter_index < len(self.chapters):
            # 更新当前章节索引
            self.current_chapter_index = chapter_index

            # 跳转到该章节开头位置
            if chapter_index in self.chapter_positions:
                pos = self.chapter_positions[chapter_index]
                line_num = float(pos.split('.')[0])
                total_lines = float(self.text_area.index('end-1c').split('.')[0])
                rel_pos = line_num / total_lines
                self.text_area.yview_moveto(rel_pos)

            # 保存位置
            self.save_current_position()

            # 更新进度显示
            self.update_progress_display()

            # 更新章节标签
            self.update_current_chapter_index()