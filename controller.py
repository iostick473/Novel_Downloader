import threading
from search import SearchEngine
from download import Downloader


class Controller:
    def __init__(self, gui):
        self.gui = gui
        self.search_engine = SearchEngine()
        self.downloader = Downloader()
        self.current_download = None  # 当前下载任务

        # 绑定GUI事件
        self.gui.search_button.config(command=self.start_search_thread)
        self.gui.download_button.config(command=self.download_selected)

    def start_search_thread(self):
        novel_name = self.gui.novel_entry.get().strip()
        if not novel_name:
            self.gui.show_warning("输入错误", "请输入小说名称")
            return

        # 禁用搜索按钮避免重复搜索
        self.gui.search_button.config(state='disabled')
        self.gui.set_status("搜索中...")

        # 获取选择的来源
        source = self.gui.source_var.get()

        # 启动新线程执行搜索
        search_thread = threading.Thread(
            target=self.search_novel,
            args=(novel_name, source),
            daemon=True
        )
        search_thread.start()

    def search_novel(self, novel_name, source):
        self.gui.log(f"开始在【{source}】搜索: {novel_name}")

        # 调用搜索引擎
        results = self.search_engine.search(source, novel_name)

        # 更新UI显示结果
        self.gui.display_results(results)

        # 启用搜索按钮
        self.gui.search_button.config(state='normal')

    def download_selected(self):
        selected = self.gui.get_selected_item()
        if not selected:
            self.gui.show_info("提示", "请先选择要下载的小说")
            return

        values = selected['values']
        novel_name = values[0]
        source = values[2]

        # 如果已有下载任务，先取消
        if self.current_download and self.current_download.is_alive():
            self.gui.log("已有下载任务进行中，等待完成...")
            return

        self.gui.log(f"开始从【{source}】下载: {novel_name}")
        self.gui.set_status("准备下载...")

        # 启动下载线程
        self.current_download = threading.Thread(
            target=self.download_novel,
            args=(novel_name, source),
            daemon=True
        )
        self.current_download.start()

    def download_novel(self, novel_name, source):
        # 调用下载器
        success = self.downloader.download(
            novel_name,
            source,
            self.update_download_progress
        )

        if success:
            self.gui.log(f"下载完成: {novel_name}")
            self.gui.set_status("下载完成")
            self.gui.show_info("下载成功", f"小说《{novel_name}》已下载完成")
        else:
            self.gui.log(f"下载失败: {novel_name}")
            self.gui.set_status("下载失败")
            self.gui.show_warning("下载失败", f"小说《{novel_name}》下载失败，请重试")

    def update_download_progress(self, novel_name, progress):
        """更新下载进度（由下载线程调用）"""
        # 使用after方法确保线程安全地更新GUI
        self.gui.root.after(0, self.gui.update_progress, novel_name, progress)