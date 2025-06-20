import tkinter as tk
from tkinter import ttk, messagebox
from database import NovelDatabase
import os


class LibraryBrowser:
    def __init__(self, root, db):
        self.root = root
        self.db = db

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
        ttk.Button(btn_frame, text="删除", command=self.delete_book).pack(side=tk.LEFT, padx=5)

        # 收藏按钮
        self.bookmark_btn = ttk.Button(btn_frame, text="收藏小说", command=self.toggle_bookmark)
        self.bookmark_btn.pack(side=tk.LEFT, padx=5)

        # 查看详情按钮
        ttk.Button(btn_frame, text="查看详情", command=self.show_book_details).pack(side=tk.LEFT, padx=5)

        # 绑定选择事件
        self.book_tree.bind("<<TreeviewSelect>>", self.on_book_select)

        # 加载分类和书籍
        self.load_categories()
        self.load_books()

    def load_categories(self):
        """加载分类列表（只保留：已下载、收藏、最近阅读）"""
        self.category_combo['values'] = ["全部", "已下载", "收藏", "最近阅读"]
        self.category_combo.current(0)

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
            books = self.db.get_bookmarked_books()
        elif selected_category == "最近阅读":
            books = self.db.get_recently_read_books()
        else:  # 全部
            books = self.db.get_all_books()

        # 添加书籍到列表
        for book in books:
            # 获取下载记录
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

    def delete_book(self):
        """删除选中的书籍"""
        selected = self.book_tree.selection()
        if not selected:
            return

        item = self.book_tree.item(selected[0])
        values = item['values']
        book_id = values[0]
        title = values[1]

        # 确认删除
        if not messagebox.askyesno("确认删除", f"确定要删除《{title}》吗？\n此操作将删除数据库记录，但不会删除文件。", parent=self.root):
            return

        # 从数据库中删除
        self.db.delete_book(book_id)

        # 重新加载书籍列表
        self.load_books()
        messagebox.showinfo("成功", f"《{title}》已从数据库中删除", parent=self.root)

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
