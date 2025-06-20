import tkinter as tk
from tkinter import ttk, messagebox
from database import NovelDatabase
import threading
import os


class LibraryBrowser:
    def __init__(self, root, db, downloader):  # 添加downloader参数
        self.root = root
        self.db = db
        self.downloader = downloader  # 保存下载器实例
        self.download_in_progress = {}  # 跟踪下载状态 {book_id: progress}

        # 创建主框架
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 顶部工具栏
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        # 搜索选项
        ttk.Label(toolbar, text="搜索范围:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_type = tk.StringVar(value="书名")  # 修复：初始值设为"书名"
        search_combo = ttk.Combobox(
            toolbar,
            textvariable=self.search_type,
            values=["书名", "作者", "全部"],
            width=8,
            state="readonly"
        )
        search_combo.pack(side=tk.LEFT, padx=5)

        # 搜索框
        ttk.Label(toolbar, text="搜索:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_entry = ttk.Entry(toolbar, width=40)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind("<KeyRelease>", self.on_search_keyrelease)

        # 清除搜索按钮
        ttk.Button(toolbar, text="清除", command=self.clear_search).pack(side=tk.LEFT, padx=5)

        # 分类筛选（保留：已下载、收藏、最近阅读）
        ttk.Label(toolbar, text="分类:").pack(side=tk.LEFT, padx=(20, 5))
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(
            toolbar,
            textvariable=self.category_var,
            width=15,
            state="readonly"
        )
        self.category_combo.pack(side=tk.LEFT, padx=5)
        self.category_combo.bind("<<ComboboxSelected>>", self.on_category_selected)

        # 刷新按钮
        ttk.Button(toolbar, text="刷新", command=self.load_books).pack(side=tk.RIGHT, padx=5)

        # 书籍列表区域
        list_frame = ttk.LabelFrame(main_frame, text="已下载小说", padding=(10, 5))
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建书籍列表树状视图
        columns = ("id", "title", "author", "source", "status", "chapters", "download_time", "progress")
        self.book_tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            selectmode="browse"
        )

        # 设置列标题
        self.book_tree.heading("title", text="书名")
        self.book_tree.heading("author", text="作者")
        self.book_tree.heading("source", text="来源")
        self.book_tree.heading("status", text="状态")
        self.book_tree.heading("chapters", text="章节数")
        self.book_tree.heading("download_time", text="下载时间")
        self.book_tree.heading("progress", text="阅读进度")

        # 设置列宽
        self.book_tree.column("title", width=200)
        self.book_tree.column("author", width=120)
        self.book_tree.column("source", width=100)
        self.book_tree.column("status", width=80)
        self.book_tree.column("chapters", width=80)
        self.book_tree.column("download_time", width=150)
        self.book_tree.column("progress", width=150)

        # 隐藏ID列
        self.book_tree.column("id", width=0, stretch=tk.NO)
        self.book_tree.heading("id", text="ID", anchor=tk.W)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.book_tree.yview)
        self.book_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.book_tree.pack(fill=tk.BOTH, expand=True)

        # 底部按钮区域
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        # 阅读按钮
        self.read_btn = ttk.Button(btn_frame, text="阅读", command=self.open_reader, state="disabled")
        self.read_btn.pack(side=tk.LEFT, padx=5)

        # 删除按钮
        ttk.Button(btn_frame, text="删除", command=self.show_delete_options).pack(side=tk.LEFT, padx=5)

        # 收藏按钮
        self.bookmark_btn = ttk.Button(btn_frame, text="收藏小说", command=self.toggle_bookmark)
        self.bookmark_btn.pack(side=tk.LEFT, padx=5)

        # 查看详情按钮
        ttk.Button(btn_frame, text="查看详情", command=self.show_book_details).pack(side=tk.LEFT, padx=5)

        # 添加下载按钮
        self.download_btn = ttk.Button(btn_frame, text="下载小说", command=self.download_novel)
        self.download_btn.pack(side=tk.LEFT, padx=5)

        # 绑定选择事件
        self.book_tree.bind("<<TreeviewSelect>>", self.on_book_select)

        # 加载分类和书籍
        self.load_categories()
        self.load_books()

        # 启动进度更新线程
        self.update_progress_thread()

    def download_novel(self):
        """下载选中的小说"""
        selected = self.book_tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选择要下载的小说", parent=self.root)
            return

        item = self.book_tree.item(selected[0])
        values = item['values']
        book_id = values[0]
        title = values[1]
        source = values[3]  # 来源信息

        # 检查是否已在下载中
        if book_id in self.download_in_progress:
            messagebox.showinfo("提示", f"《{title}》正在下载中，请勿重复操作", parent=self.root)
            return

        # 确认下载
        if not messagebox.askyesno("确认", f"确定要下载《{title}》吗？", parent=self.root):
            return

        # 标记为下载中
        self.download_in_progress[book_id] = 0

        # 在单独的线程中执行下载
        threading.Thread(
            target=self._download_thread,
            args=(book_id, source, title),
            daemon=True
        ).start()

    def _download_thread(self, book_id, source, title):
        """下载线程"""
        try:
            # 进度回调函数
            def progress_callback(n_id, progress):
                if n_id == book_id:
                    self.download_in_progress[book_id] = progress

            # 执行下载
            success = self.downloader.download(book_id, source, progress_callback)

            # 下载完成后更新状态
            if success:
                # 更新数据库
                downloads = self.downloader.get_download_info(book_id)
                if downloads and self.db:
                    # 修复：传递文件路径字符串而不是字典
                    self.db.record_download(book_id, downloads[0]['file_path'])

                # 刷新列表
                self.root.after(0, lambda: self.load_books())
                self.root.after(0, lambda: self.safe_show_info("成功", f"《{title}》下载完成"))
            else:
                self.root.after(0, lambda: self.safe_show_error("错误", f"《{title}》下载失败"))
        except Exception as e:
            # 使用局部变量捕获异常信息
            error_msg = str(e)
            self.root.after(0, lambda: self.safe_show_warning("错误", f"下载出错: {error_msg}"))
        finally:
            # 移除下载状态
            if book_id in self.download_in_progress:
                del self.download_in_progress[book_id]

    def update_progress_thread(self):
        """定期更新下载进度显示"""
        for book_id, progress in self.download_in_progress.items():
            # 在树状视图中更新进度
            for item in self.book_tree.get_children():
                values = self.book_tree.item(item)['values']
                if values and values[0] == book_id:
                    # 创建新的值列表，更新进度列
                    new_values = list(values)
                    new_values[7] = f"下载中: {progress}%"  # 第8列是进度
                    self.book_tree.item(item, values=new_values)
                    break

        # 每500毫秒更新一次
        self.root.after(500, self.update_progress_thread)

    def load_categories(self):
        """加载分类列表（只保留：已下载、收藏、最近阅读）"""
        self.category_combo['values'] = ["全部", "已下载", "收藏", "最近阅读"]
        self.category_combo.current(0)

    def safe_show_info(self, title, message):
        if self.root.winfo_exists():
            messagebox.showinfo(title, message, parent=self.root)

    def safe_show_error(self, title, message):
        if self.root.winfo_exists():
            messagebox.showerror(title, message, parent=self.root)

    def safe_show_warning(self, title, message):
        if self.root.winfo_exists():
            messagebox.showwarning(title, message, parent=self.root)

    def on_category_selected(self, event=None):
        """当选择分类时重新加载书籍"""
        self.load_books()

    def load_books(self):
        """加载书籍列表"""
        # 清空现有书籍
        for item in self.book_tree.get_children():
            self.book_tree.delete(item)

        # 获取当前选择的分类
        selected_category = self.category_var.get()

        # 根据分类获取书籍
        if selected_category == "已下载":
            books = self.db.get_books_in_category("已下载")
        elif selected_category == "收藏":
            # 获取所有收藏书籍（包括未下载的）
            books = self.db.get_bookmarked_books()
        elif selected_category == "最近阅读":
            books = self.db.get_recently_read_books()
        else:  # 全部
            # 获取所有书籍（包括收藏但未下载的）
            books = self.db.get_all_books()

        # 添加书籍到列表
        for book in books:
            # 获取下载记录（未下载的书籍可能没有下载记录）
            downloads = self.db.get_book_downloads(book['id'])
            download_time = ""
            if downloads:
                download_time = downloads[0]['download_time']
                if isinstance(download_time, str):
                    download_time = download_time[:16]  # 截取日期和时间部分

            # 获取阅读进度
            progress = self.db.get_reading_progress(book['id'])
            progress_text = "未开始阅读"
            if progress:
                current_chapter = progress.get('current_chapter', 1)
                total_chapters = book.get('total_chapters', 0)
                if total_chapters > 0:
                    progress_text = f"{current_chapter}/{total_chapters}章"
                else:
                    progress_text = f"第{current_chapter}章"

                if progress.get('bookmarked'):
                    progress_text += " ⭐"

            # 添加书籍到树状视图
            self.book_tree.insert("", "end", values=(
                book['id'],
                book['title'],
                book['author'],
                book.get('source', '未知来源'),
                book.get('status', '未知状态'),
                book.get('chapters', '未知'),
                download_time,
                progress_text
            ))

    def on_search_keyrelease(self, event):
        """实时搜索处理"""
        self.search_books()

    def clear_search(self):
        """清除搜索条件"""
        self.search_entry.delete(0, tk.END)
        self.load_books()

    def search_books(self):
        """搜索书籍"""
        keyword = self.search_entry.get().strip()
        if not keyword:
            self.load_books()
            return

        search_type = self.search_type.get()
        if search_type == "书名":
            books = self.db.search_books_by_title(keyword)
        elif search_type == "作者":
            books = self.db.search_books_by_author(keyword)
        else:  # 全部
            books = self.db.search_books(keyword)

        # 清空现有书籍
        for item in self.book_tree.get_children():
            self.book_tree.delete(item)

        # 添加搜索结果
        for book in books:
            # 获取下载记录
            downloads = self.db.get_book_downloads(book['id'])
            download_time = ""
            if downloads:
                download_time = downloads[0]['download_time']
                if isinstance(download_time, str):
                    download_time = download_time[:16]

            # 获取阅读进度
            progress = self.db.get_reading_progress(book['id'])
            progress_text = "未开始阅读"
            if progress:
                current_chapter = progress.get('current_chapter', 1)
                total_chapters = book.get('chapters', "未知章节数")
                if isinstance(total_chapters, str) and "章" in total_chapters:
                    try:
                        total_chapters = int(total_chapters.split("章")[0])
                    except:
                        total_chapters = 1
                progress_text = f"{current_chapter}/{total_chapters}章"

                if progress.get('bookmarked'):
                    progress_text += " 📖"

            self.book_tree.insert("", "end", values=(
                book['id'],
                book['title'],
                book['author'],
                book.get('source', '未知来源'),
                book.get('status', '未知状态'),
                book.get('chapters', '未知'),
                download_time,
                progress_text
            ))

    def on_book_select(self, event):
        """当书籍被选中时"""
        selected = self.book_tree.selection()
        if selected:
            self.read_btn.config(state="normal")
            item = self.book_tree.item(selected[0])
            values = item['values']
            book_id = values[0]  # 第一列是ID

            progress = self.db.get_reading_progress(book_id)
            bookmarked = progress.get('bookmarked', False) if progress else False

            if bookmarked:
                self.bookmark_btn.config(text="取消收藏")
            else:
                self.bookmark_btn.config(text="收藏小说")
        else:
            self.read_btn.config(state="disabled")
            self.bookmark_btn.config(text="收藏小说")  # 无选中时恢复默认文本

    def open_reader(self):
        """打开阅读器"""
        selected = self.book_tree.selection()
        if not selected:
            return

        item = self.book_tree.item(selected[0])
        values = item['values']
        book_id = values[0]  # 第一列是ID

        # 获取下载记录
        downloads = self.db.get_book_downloads(book_id)
        if not downloads:
            messagebox.showwarning("错误", "该书没有下载记录", parent=self.root)
            return

        # 获取文件路径
        file_path = downloads[0]['file_path']

        # 检查文件是否存在
        if not os.path.exists(file_path):
            messagebox.showwarning("错误", "小说文件不存在", parent=self.root)
            return

        # 创建阅读器窗口
        reader_window = tk.Toplevel(self.root)
        reader_window.title(f"阅读: {values[1]}")
        reader_window.geometry("1000x700")

        # 导入阅读器模块
        from reader import NovelReader
        NovelReader(reader_window, self.db, book_id, file_path)

    def show_delete_options(self):
        """显示删除选项对话框"""
        selected = self.book_tree.selection()
        if not selected:
            return

        item = self.book_tree.item(selected[0])
        values = item['values']
        self.selected_book_id = values[0]
        self.selected_title = values[1]

        option_dialog = tk.Toplevel(self.root)
        option_dialog.title("删除选项")
        option_dialog.geometry("300x150")
        option_dialog.transient(self.root)
        option_dialog.grab_set()

        # 添加标签
        label = ttk.Label(option_dialog, text=f"请选择删除《{self.selected_title}》的方式：")
        label.pack(pady=10)

        # 按钮框架
        btn_frame = ttk.Frame(option_dialog)
        btn_frame.pack(pady=10)

        # 三个选项按钮
        ttk.Button(
            btn_frame,
            text="仅删除文件",
            command=lambda: self.delete_book(option_dialog, delete_file=True, delete_db=False)
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="仅删除数据库数据",
            command=lambda: self.delete_book(option_dialog, delete_file=False, delete_db=True)
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="同时删除",
            command=lambda: self.delete_book(option_dialog, delete_file=True, delete_db=True)
        ).pack(side=tk.LEFT, padx=5)

    def delete_book(self, dialog, delete_file=False, delete_db=False):
        """根据选项删除书籍"""
        if not delete_file and not delete_db:
            dialog.destroy()
            return

        # 获取下载记录
        downloads = self.db.get_book_downloads(self.selected_book_id)
        file_path = downloads[0]['file_path'] if downloads else None

        # 删除文件
        if delete_file and file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                file_deleted = True
            except Exception as e:
                messagebox.showerror("错误", f"文件删除失败: {str(e)}", parent=dialog)
                file_deleted = False
        else:
            file_deleted = False

        # 删除数据库数据
        if delete_db:
            self.db.delete_book(self.selected_book_id)
            db_deleted = True
        else:
            db_deleted = False

        # 显示结果消息
        messages = []
        if file_deleted:
            messages.append("文件已删除")
        if db_deleted:
            messages.append("数据库数据已删除")

        if messages:
            messagebox.showinfo("成功", f"《{self.selected_title}》" + "，".join(messages), parent=dialog)
        else:
            messagebox.showwarning("警告", "未执行任何删除操作", parent=dialog)

        # 关闭对话框并刷新列表
        dialog.destroy()
        self.load_books()

    def toggle_bookmark(self):
        """切换收藏状态"""
        selected = self.book_tree.selection()
        if not selected:
            return

        item = self.book_tree.item(selected[0])
        values = item['values']
        book_id = values[0]
        title = values[1]

        # 切换收藏状态
        self.db.toggle_bookmark(book_id)

        # 重新加载书籍列表
        self.load_books()

        progress = self.db.get_reading_progress(book_id)
        bookmarked = progress.get('bookmarked', False) if progress else False

        if bookmarked:
            self.bookmark_btn.config(text="取消收藏")
            # 指定父窗口为当前LibraryBrowser窗口
            messagebox.showinfo("成功", f"已收藏《{title}》", parent=self.root)
        else:
            self.bookmark_btn.config(text="收藏小说")
            # 指定父窗口为当前LibraryBrowser窗口
            messagebox.showinfo("成功", f"已取消收藏《{title}》", parent=self.root)

    def show_book_details(self):
        """显示书籍详情"""
        selected = self.book_tree.selection()
        if not selected:
            return

        item = self.book_tree.item(selected[0])
        values = item['values']
        book_id = values[0]

        # 获取书籍信息
        book = self.db.get_book(book_id)
        if not book:
            return

        # 获取下载记录
        downloads = self.db.get_book_downloads(book_id)
        download_info = "无下载记录"
        if downloads:
            download_info = f"下载时间: {downloads[0]['download_time']}\n文件路径: {downloads[0]['file_path']}"

        # 获取阅读进度
        progress = self.db.get_reading_progress(book_id)
        progress_info = "未开始阅读"
        if progress:
            progress_info = f"当前章节: {progress.get('current_chapter', 1)}\n阅读位置: {int(progress.get('chapter_position', 0) * 100)}%"
            if progress.get('bookmarked'):
                progress_info += "\n已收藏"

        # 创建详情窗口
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"书籍详情: {book['title']}")
        detail_window.geometry("500x400")

        # 创建主框架
        main_frame = ttk.Frame(detail_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 书籍信息
        info_frame = ttk.LabelFrame(main_frame, text="书籍信息")
        info_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(info_frame, text=f"书名: {book['title']}").pack(anchor=tk.W, padx=5, pady=2)
        ttk.Label(info_frame, text=f"作者: {book['author']}").pack(anchor=tk.W, padx=5, pady=2)
        ttk.Label(info_frame, text=f"来源: {book.get('source', '未知来源')}").pack(anchor=tk.W, padx=5, pady=2)
        ttk.Label(info_frame, text=f"状态: {book.get('status', '未知状态')}").pack(anchor=tk.W, padx=5, pady=2)
        ttk.Label(info_frame, text=f"章节数: {book.get('chapters', '未知')}").pack(anchor=tk.W, padx=5, pady=2)

        # 下载信息
        download_frame = ttk.LabelFrame(main_frame, text="下载信息")
        download_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(download_frame, text=download_info).pack(anchor=tk.W, padx=5, pady=2)

        # 阅读进度
        progress_frame = ttk.LabelFrame(main_frame, text="阅读进度")
        progress_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(progress_frame, text=progress_info).pack(anchor=tk.W, padx=5, pady=2)

        # 分类信息
        categories = self.db.get_book_categories(book_id)
        if categories:
            category_frame = ttk.LabelFrame(main_frame, text="分类")
            category_frame.pack(fill=tk.X, padx=5, pady=5)

            categories_text = ", ".join(categories)
            ttk.Label(category_frame, text=categories_text).pack(anchor=tk.W, padx=5, pady=2)

        # 关闭按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        ttk.Button(btn_frame, text="关闭", command=detail_window.destroy).pack(side=tk.RIGHT, padx=5)
