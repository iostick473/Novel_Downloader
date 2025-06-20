import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from database import NovelDatabase
from download import Downloader
from controller import Controller
from library_browser import LibraryBrowser
import os


class NovelDownloaderApp:
    def __init__(self, root):
        self.root = root
        root.title("小说下载器 v3.0")
        root.geometry("800x600")
        root.resizable(True, True)

        # 控制器引用
        self.controller = None

        # 创建主框架
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 顶部来源选择区域
        source_frame = ttk.Frame(main_frame)
        source_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        ttk.Label(source_frame, text="下载来源:").pack(side=tk.LEFT, padx=(0, 5))

        # 来源选择下拉框
        self.source_var = tk.StringVar()
        self.source_combobox = ttk.Combobox(
            source_frame,
            textvariable=self.source_var,
            width=15,
            state="readonly"
        )
        self.source_combobox['values'] = ('起点中文网', '晋江文学城')
        self.source_combobox.current(0)
        self.source_combobox.pack(side=tk.LEFT)

        # 添加阅读器按钮
        ttk.Button(source_frame, text="阅读器", command=self.open_library_browser).pack(side=tk.RIGHT, padx=10)

        # 搜索区域
        search_frame = ttk.LabelFrame(main_frame, text="搜索小说", padding=(10, 5))
        search_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(search_frame, text="小说名称:").grid(row=0, column=0, padx=5, pady=5)
        self.novel_entry = ttk.Entry(search_frame, width=40)
        self.novel_entry.grid(row=0, column=1, padx=5, pady=5)

        # 按钮
        self.search_button = ttk.Button(search_frame, text="搜索")
        self.search_button.grid(row=0, column=2, padx=5)

        self.download_button = ttk.Button(search_frame, text="下载选中")
        self.download_button.grid(row=0, column=3, padx=5)

        # 取消下载按钮
        self.cancel_button = ttk.Button(search_frame, text="取消下载", state="disabled")
        self.cancel_button.grid(row=0, column=4, padx=5)

        # 在搜索区域添加收藏按钮
        self.favorite_button = ttk.Button(search_frame, text="收藏选中")
        self.favorite_button.grid(row=0, column=5, padx=5)  # 放在取消按钮后面

        # 结果列表区域
        result_frame = ttk.LabelFrame(main_frame, text="搜索结果", padding=(10, 5))
        result_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("id", "title", "author", "source", "status", "chapters")
        self.result_tree = ttk.Treeview(
            result_frame,
            columns=columns,
            show="headings",
            selectmode="browse"
        )

        # 设置列标题
        self.result_tree.heading("title", text="书名")
        self.result_tree.heading("author", text="作者")
        self.result_tree.heading("source", text="来源")
        self.result_tree.heading("status", text="状态")
        self.result_tree.heading("chapters", text="章节数")

        # 设置列宽
        self.result_tree.column("title", width=200)
        self.result_tree.column("author", width=120)
        self.result_tree.column("source", width=100)
        self.result_tree.column("status", width=80)
        self.result_tree.column("chapters", width=80)

        # 隐藏ID列
        self.result_tree.column("id", width=0, stretch=tk.NO)
        self.result_tree.heading("id", text="ID", anchor=tk.W)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.result_tree.yview)
        self.result_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_tree.pack(fill=tk.BOTH, expand=True)

        # 下载进度区域
        progress_frame = ttk.LabelFrame(main_frame, text="下载进度", padding=(10, 5))
        progress_frame.pack(fill=tk.X, padx=5, pady=5)

        self.progress_var = tk.StringVar(value="等待下载...")
        ttk.Label(progress_frame, textvariable=self.progress_var).pack(anchor=tk.W)

        self.progress = ttk.Progressbar(progress_frame, orient="horizontal", length=600, mode="determinate")
        self.progress.pack(fill=tk.X, pady=5)

        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="下载日志", padding=(10, 5))
        log_frame.pack(fill=tk.BOTH, padx=5, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=8)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.configure(state='disabled')

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # 创建菜单
        self.create_menu()

    def set_controller(self, controller):
        """设置控制器实例"""
        self.controller = controller
        # 绑定收藏按钮事件
        self.favorite_button.config(command=self.controller.toggle_favorite)

    def open_library_browser(self):
        """打开图书馆浏览器"""
        library_window = tk.Toplevel(self.root)
        library_window.title("小说图书馆")
        library_window.geometry("1000x700")
        LibraryBrowser(library_window, self.controller.db, self.controller.downloader)

    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="数据库设置", command=self.open_db_settings)
        menubar.add_cascade(label="设置", menu=settings_menu)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="打开下载目录", command=self.open_download_dir)
        # 移除了退出选项
        menubar.add_cascade(label="文件", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于", command=self.show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)

        # 移除了"阅读"菜单

    def open_db_settings(self):
        SettingsDialog(self.root, self.controller.db)

    def open_download_dir(self):
        download_dir = "downloads"
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)

        try:
            os.startfile(download_dir)
        except:
            try:
                os.system(f'open "{download_dir}"')
            except:
                try:
                    os.system(f'xdg-open "{download_dir}"')
                except:
                    self.show_info("打开目录", f"下载目录: {os.path.abspath(download_dir)}")

    def show_about(self):
        messagebox.showinfo("关于小说下载器", "版本: 1.14\n使用小说编号作为唯一标识")

    def get_selected_item(self):
        selected = self.result_tree.selection()
        if not selected:
            return None

        # 返回包含所有字段的字典
        item = self.result_tree.item(selected[0])
        return item['values']

    def open_reader(self, event):
        """双击打开阅读器"""
        selected = self.result_tree.selection()
        if not selected:
            return

        item = self.result_tree.item(selected[0])
        values = item['values']

        # 获取书籍ID
        book_id = values[0]  # 假设ID在第一列

        # 通过控制器打开阅读器
        if self.controller:
            self.controller.open_novel(book_id)

    def display_results(self, results):
        # 清空结果列表
        self.result_tree.delete(*self.result_tree.get_children())
        # 绑定双击事件
        self.result_tree.bind("<Double-1>", self.open_reader)

        if not results:
            self.log("没有找到相关结果")
            self.set_status("搜索完成，没有结果")
            return

        for result in results:
            # 提取要显示的字段
            values = (
                result["id"],  # ID (隐藏)
                result["title"],  # 书名
                result["author"],  # 作者
                result["source"],  # 来源
                result["status"],  # 状态
                result["chapters"]  # 章节数
            )
            self.result_tree.insert("", "end", values=values)

        self.log(f"找到{len(results)}个相关结果")
        self.set_status(f"搜索完成，找到{len(results)}个结果")

    def update_progress(self, novel_id, progress):
        """更新下载进度"""
        # 从ID中提取书名
        if "_" in novel_id:
            novel_title = novel_id.split("_", 1)[1]
        else:
            novel_title = novel_id

        self.progress_var.set(f"下载中: {novel_title} [{progress}%]")
        self.progress['value'] = progress
        self.log(f"下载进度: {novel_title} [{progress}%]")
        self.set_status(f"下载中: {progress}%")

    def log(self, message):
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.configure(state='disabled')
        self.log_text.yview(tk.END)

    def set_status(self, message):
        self.status_var.set(message)

    def show_warning(self, title, message):
        messagebox.showwarning(title, message)

    def show_info(self, title, message):
        messagebox.showinfo(title, message)


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.title("数据库设置")
        self.db = db

        ttk.Label(self, text="当前数据库位置:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        current_path = ttk.Label(self, text=db.db_path)
        current_path.grid(row=0, column=1, padx=10, pady=10)

        ttk.Label(self, text="新数据库文件夹:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.new_path = ttk.Entry(self, width=50)
        self.new_path.grid(row=1, column=1, padx=10, pady=10)

        ttk.Button(self, text="浏览...", command=self.browse).grid(row=1, column=2, padx=10, pady=10)

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=20)

        ttk.Button(btn_frame, text="应用", command=self.apply).pack(side=tk.RIGHT, padx=10)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.RIGHT)

    def browse(self):
        # 选择文件夹而不是文件
        path = filedialog.askdirectory(title="选择数据库文件夹")
        if path:
            self.new_path.delete(0, tk.END)
            self.new_path.insert(0, path)

    def apply(self):
        new_folder = self.new_path.get()
        if new_folder:
            self.db.set_custom_db_path(new_folder)
            messagebox.showinfo("成功", f"数据库文件夹已更新为:\n{new_folder}")
            self.destroy()
