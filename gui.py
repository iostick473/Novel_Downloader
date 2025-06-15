import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import os


class NovelDownloaderApp:
    def __init__(self, root):
        self.root = root
        root.title("小说下载器 v2.0")
        root.geometry("800x600")
        root.resizable(True, True)

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

        # 结果列表区域
        result_frame = ttk.LabelFrame(main_frame, text="搜索结果", padding=(10, 5))
        result_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("name", "author", "source", "status", "chapters")
        self.result_tree = ttk.Treeview(
            result_frame,
            columns=columns,
            show="headings",
            selectmode="browse"
        )

        # 设置列标题
        self.result_tree.heading("name", text="书名")
        self.result_tree.heading("author", text="作者")
        self.result_tree.heading("source", text="来源")
        self.result_tree.heading("status", text="状态")
        self.result_tree.heading("chapters", text="章节数")

        # 设置列宽
        self.result_tree.column("name", width=200)
        self.result_tree.column("author", width=120)
        self.result_tree.column("source", width=100)
        self.result_tree.column("status", width=80)
        self.result_tree.column("chapters", width=80)

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

        # 添加示例数据
        self.add_sample_data()

    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="打开下载目录", command=self.open_download_dir)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        menubar.add_cascade(label="文件", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于", command=self.show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)

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
        messagebox.showinfo("关于小说下载器", "版本: 2.0\n使用多线程实现高效搜索和下载")

    def get_selected_item(self):
        selected = self.result_tree.selection()
        if not selected:
            return None
        return self.result_tree.item(selected[0])

    def display_results(self, results):
        self.result_tree.delete(*self.result_tree.get_children())

        if not results:
            self.log("没有找到相关结果")
            self.set_status("搜索完成，没有结果")
            return

        for result in results:
            self.result_tree.insert("", "end", values=result)

        self.log(f"找到{len(results)}个相关结果")
        self.set_status(f"搜索完成，找到{len(results)}个结果")

    def update_progress(self, novel_name, progress):
        """更新下载进度"""
        self.progress_var.set(f"下载中: {novel_name} [{progress}%]")
        self.progress['value'] = progress
        self.log(f"下载进度: {novel_name} [{progress}%]")
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

    def add_sample_data(self):
        sample_data = [
            ("诡秘之主", "爱潜水的乌贼", "起点中文网", "已完结", "1434章"),
            ("斗破苍穹", "天蚕土豆", "起点中文网", "已完结", "1623章"),
            ("镇魂", "Priest", "晋江文学城", "已完结", "112章"),
            ("魔道祖师", "墨香铜臭", "晋江文学城", "已完结", "126章"),
        ]

        for data in sample_data:
            self.result_tree.insert("", "end", values=data)

        self.log("已加载示例数据，可以尝试搜索或直接下载")