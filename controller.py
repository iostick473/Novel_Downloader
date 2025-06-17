import threading
import os
import tkinter as tk
from search import SearchEngine
from download import Downloader
from database import NovelDatabase
from reader import NovelReader


class Controller:
    def __init__(self, gui):
        self.gui = gui
        self.search_engine = SearchEngine()
        self.downloader = Downloader()
        self.current_download = None  # 当前下载任务
        self.db = NovelDatabase()  # 创建数据库实例

        # 绑定GUI事件
        self.gui.search_button.config(command=self.start_search_thread)
        self.gui.download_button.config(command=self.download_selected)

        # 设置控制器引用到GUI
        self.gui.set_controller(self)

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

        # 获取小说ID和来源
        novel_id = selected[0]  # 第一列是ID
        source = selected[3]  # 第四列是来源

        # 获取小说标题用于日志
        novel_title = selected[1]

        # 如果已有下载任务，先取消
        if self.current_download and self.current_download.is_alive():
            self.gui.log("已有下载任务进行中，等待完成...")
            return

        self.gui.log(f"开始从【{source}】下载: {novel_title} (ID: {novel_id})")
        self.gui.set_status("准备下载...")

        # 启动下载线程
        self.current_download = threading.Thread(
            target=self.download_novel,
            args=(novel_id, source),
            daemon=True
        )
        self.current_download.start()

    def download_novel(self, novel_id, source):
        # 调用下载器
        success = self.downloader.download(
            novel_id,
            source,
            self.update_download_progress
        )

        # 从ID中提取书名
        if "_" in novel_id:
            novel_title = novel_id.split("_", 1)[1]
        else:
            novel_title = novel_id

        if success:
            self.gui.log(f"下载完成: {novel_title} (ID: {novel_id})")
            self.gui.set_status("下载完成")
            self.gui.show_info("下载成功", f"小说《{novel_title}》已下载完成")
        else:
            self.gui.log(f"下载失败: {novel_title} (ID: {novel_id})")
            self.gui.set_status("下载失败")
            self.gui.show_warning("下载失败", f"小说《{novel_title}》下载失败，请重试")

    def update_download_progress(self, novel_id, progress):
        """更新下载进度（由下载线程调用）"""
        # 使用after方法确保线程安全地更新GUI
        self.gui.root.after(0, self.gui.update_progress, novel_id, progress)

    def open_novel(self, book_id):
        """打开小说阅读器"""
        # 获取书籍信息
        book_info = self.db.get_book(book_id)
        if not book_info:
            self.gui.show_warning("错误", "未找到书籍信息")
            return

        # 获取下载记录
        downloads = self.db.get_book_downloads(book_id)
        if not downloads:
            self.gui.show_warning("错误", "该书没有下载记录")
            return

        # 获取文件路径
        file_path = downloads[0]['file_path']

        # 检查文件是否存在
        if not os.path.exists(file_path):
            self.gui.show_warning("错误", "小说文件不存在")
            return

        # 创建阅读器窗口
        reader_window = tk.Toplevel(self.gui.root)
        reader_window.title(f"阅读: {book_info['title']}")
        reader_window.geometry("1000x700")

        # 导入阅读器模块
        NovelReader(reader_window, self.db, book_id, file_path)

    def save_reading_progress(self, book_id, chapter_index, position):
        """保存阅读进度"""
        self.db.save_reading_progress(book_id, chapter_index, position)

    def record_reading_session(self, book_id, duration, chapters_read):
        """记录阅读会话"""
        self.db.add_reading_history(book_id, duration, chapters_read)

    def toggle_bookmark(self, book_id):
        """切换书签状态"""
        return self.db.toggle_bookmark(book_id)

    def get_recently_read(self):
        """获取最近阅读的书籍"""
        return self.db.get_recently_read_books(limit=5)
