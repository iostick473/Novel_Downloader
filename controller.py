import threading
from search import SearchEngine
from download import Downloader


class Controller:
    def __init__(self, gui):
        self.gui = gui
        self.search_engine = SearchEngine()
        self.downloader = Downloader()

        # 绑定GUI事件
        self.gui.search_button.config(command=self.start_search_thread)
        self.gui.download_button.config(command=self.download_selected)

    def start_search_thread(self):
        """启动搜索线程"""
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
        """搜索小说功能"""
        self.gui.log(f"开始在【{source}】搜索: {novel_name}")

        # 调用搜索引擎
        results = self.search_engine.search(source, novel_name)

        # 更新UI显示结果
        self.gui.display_results(results)

        # 启用搜索按钮
        self.gui.search_button.config(state='normal')

    def download_selected(self):
        """下载选中小说功能"""
        selected = self.gui.get_selected_item()
        if not selected:
            self.gui.show_info("提示", "请先选择要下载的小说")
            return

        values = selected['values']
        novel_name = values[0]
        source = values[2]

        self.gui.log(f"开始从【{source}】下载: {novel_name}")
        self.gui.set_status("准备下载...")

        # 启动下载线程
        download_thread = threading.Thread(
            target=self.download_novel,
            args=(novel_name, source),
            daemon=True
        )
        download_thread.start()

    def download_novel(self, novel_name, source):
        """下载小说功能"""
        # 调用下载器
        success = self.downloader.download(
            novel_name,
            source,
            self.gui.update_progress
        )

        if success:
            self.gui.log(f"下载完成: {novel_name}")
            self.gui.set_status("下载完成")
            self.gui.show_info("下载成功", f"小说《{novel_name}》已下载完成")
        else:
            self.gui.log(f"下载失败: {novel_name}")
            self.gui.set_status("下载失败")
            self.gui.show_warning("下载失败", f"小说《{novel_name}》下载失败，请重试")