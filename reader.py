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
        self.bookmarked = False  # 书签状态
        self.reading_progress = None  # 阅读进度
        self.reading_start_time = datetime.now()  # 开始阅读时间
        self.night_mode = False  # 夜间模式
        self.notes_text = None  # 笔记文本框

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

        # 加载当前章节
        if self.chapters:
            self.display_current_chapter()
        else:
            messagebox.showerror("错误", "无法加载小说内容")

        # 设置窗口关闭事件
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 跟踪阅读时间
        self.root.after(60000, self.update_reading_time)

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

        # 绑定滚动事件以更新位置
        self.text_area.bind("<MouseWheel>", self.update_position)
        self.text_area.bind("<Button-4>", self.update_position)  # Linux向上滚动
        self.text_area.bind("<Button-5>", self.update_position)  # Linux向下滚动
        self.text_area.bind("<Key>", self.update_position)  # 键盘导航

    def prev_chapter(self):
        """跳转到上一章"""
        if self.current_chapter_index > 0:
            self.current_chapter_index -= 1
            self.display_current_chapter()

    def next_chapter(self):
        """跳转到下一章"""
        if self.current_chapter_index < len(self.chapters) - 1:
            self.current_chapter_index += 1
            self.display_current_chapter()

    def add_bookmark(self):
        """添加书签"""
        # 获取当前章节和位置
        current_chapter = self.current_chapter_index + 1
        position = self.get_scroll_position()
        note = self.notes_text.get("1.0", tk.END).strip()  # 获取笔记内容

        # 在后台线程中执行数据库操作
        threading.Thread(
            target=self._save_bookmark_in_thread,
            args=(self.book_id, current_chapter, position, note),
            daemon=True
        ).start()

        # 更新UI状态
        self.bookmarked = True
        self.update_bookmark_button()

        # 显示成功消息（非阻塞方式）
        self.show_status_message("书签已添加")

    def _save_bookmark_in_thread(self, book_id, chapter, position, note):
        """在后台线程中保存书签"""
        try:
            # 创建新的数据库连接（避免线程安全问题）
            from database import NovelDatabase
            db = NovelDatabase(self.db.db_path)  # 使用相同的数据库路径

            # 保存书签
            db.add_bookmark(book_id, chapter, position, note)
        except Exception as e:
            # 在主线程显示错误
            self.root.after(0, lambda: messagebox.showerror("错误", f"保存书签失败: {e}"))

    def display_current_chapter(self):
        """显示当前章节内容"""
        if not self.chapters or self.current_chapter_index >= len(self.chapters):
            return

        chapter = self.chapters[self.current_chapter_index]

        # 更新章节标签
        self.chapter_label.config(text=f"章节: {self.current_chapter_index + 1}/{len(self.chapters)}")

        # 更新文本内容
        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete(1.0, tk.END)
        self.text_area.insert(tk.END, f"{chapter['title']}\n\n{chapter['content']}")
        self.text_area.config(state=tk.DISABLED)

        # 恢复滚动位置
        if self.reading_progress and self.current_chapter_index + 1 == self.reading_progress.get('current_chapter', 1):
            position = self.reading_progress.get('chapter_position', 0)
            self.text_area.yview_moveto(position)

    def load_reading_progress(self):
        """从数据库加载阅读进度"""
        self.reading_progress = self.db.get_reading_progress(self.book_id)

        if self.reading_progress:
            # 从数据库加载书签状态
            self.bookmarked = bool(self.reading_progress.get('bookmarked', False))
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

        # 更新书签按钮状态
        self.update_bookmark_button()

    def load_novel_content(self):
        """加载小说内容"""
        try:
            # 尝试解析小说内容
            self.chapters = self.parse_novel_content()

            if not self.chapters:
                messagebox.showerror("错误", "无法解析小说内容")
                return

            # 设置当前章节索引
            if self.reading_progress:
                # 确保进度中的章节索引在有效范围内
                progress_chapter = self.reading_progress.get('current_chapter', 1)
                self.current_chapter_index = max(0, min(progress_chapter - 1, len(self.chapters) - 1))
            else:
                self.current_chapter_index = 0

            # 显示当前章节
            self.display_current_chapter()
        except Exception as e:
            messagebox.showerror("错误", f"加载小说内容失败: {e}")
            # 设置默认值
            self.chapters = []
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
            # 使用字典格式访问章节标题
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

    def get_scroll_position(self):
        """获取当前滚动位置（0.0到1.0）"""
        if hasattr(self, 'text_area'):
            return self.text_area.yview()[0]
        return 0.0

    def update_position(self, event=None):
        """更新阅读位置"""
        # 获取当前滚动位置（0.0到1.0）
        position = self.text_area.yview()[0]
        self.reading_progress['chapter_position'] = position

        # 自动保存位置（每30秒一次）
        if not hasattr(self, 'last_save_time') or (datetime.now() - self.last_save_time).seconds > 30:
            self.save_current_position()

    def save_current_position(self):
        """保存当前阅读位置到数据库"""
        if not self.chapters:
            return

        # 获取当前章节索引（从1开始）
        current_chapter = self.current_chapter_index + 1
        # 获取当前章节内的滚动位置（0.0到1.0）
        position = self.get_scroll_position()

        # 安全获取书签状态
        bookmarked = getattr(self, 'bookmarked', False)

        # 安全获取笔记内容
        notes = ""
        if hasattr(self, 'notes_text'):
            try:
                notes = self.notes_text.get("1.0", tk.END).strip()
            except:
                pass

        # 保存进度 - 使用线程避免阻塞UI
        threading.Thread(
            target=self.db.save_reading_progress,
            args=(
                self.book_id,
                current_chapter,
                position,
                bookmarked,
                notes
            ),
            daemon=True
        ).start()

    def toggle_bookmark(self):
        """切换书签状态 - 修复卡死问题"""
        # 先更新UI状态
        self.bookmarked = not self.bookmarked
        self.update_bookmark_button()

        # 在后台线程中更新数据库
        def db_operation():
            try:
                # 调用数据库方法切换书签
                self.db.toggle_bookmark(self.book_id)

                # 更新UI状态
                status = "已添加" if self.bookmarked else "已移除"
                self.root.after(0, lambda: messagebox.showinfo("书签", f"{status}书签"))
            except Exception as e:
                # 如果出错，恢复原来的状态
                self.bookmarked = not self.bookmarked
                self.root.after(0, self.update_bookmark_button)
                self.root.after(0, lambda: messagebox.showerror("错误", f"更新书签失败: {e}"))

        # 启动后台线程
        threading.Thread(target=db_operation, daemon=True).start()

    def update_bookmark_button(self):
        """更新书签按钮状态 - 修复卡死问题"""
        if hasattr(self, 'bookmark_btn'):
            if self.bookmarked:
                self.bookmark_btn.config(text="★ 已书签")
            else:
                self.bookmark_btn.config(text="☆ 添加书签")


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
        """窗口关闭事件处理"""
        # 保存当前位置 - 使用同步方式确保在关闭前保存
        if hasattr(self, 'chapters') and self.chapters:
            # 安全获取当前章节索引
            current_chapter_index = getattr(self, 'current_chapter_index', 0)
            current_chapter = current_chapter_index + 1

            # 安全获取滚动位置
            position = 0.0
            if hasattr(self, 'get_scroll_position'):
                try:
                    position = self.get_scroll_position()
                except:
                    pass

            # 安全获取书签状态
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

        # 记录阅读时间
        if hasattr(self, 'reading_start_time'):
            # 确保使用 datetime.now() 而不是 datetime.datetime.now()
            reading_time = (datetime.now() - self.reading_start_time).total_seconds()
            current_chapter = getattr(self, 'current_chapter_index', 0) + 1

            # 检查数据库是否有 record_reading_time 方法
            if hasattr(self.db, 'record_reading_time'):
                self.db.record_reading_time(self.book_id, reading_time, current_chapter)
            else:
                # 如果方法不存在，打印警告
                print("警告: 数据库缺少 record_reading_time 方法")

        # 关闭窗口
        self.root.destroy()

    def on_scroll(self, event):
        """处理滚动事件"""
        # 更新滚动位置
        self.update_scroll_position()

        # 延迟保存位置 - 避免频繁保存
        if hasattr(self, 'save_timer'):
            self.root.after_cancel(self.save_timer)
        self.save_timer = self.root.after(2000, self.save_current_position)  # 2秒后保存