import requests
import os
import time
import random
import re
from bs4 import BeautifulSoup
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


class Downloader:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        self.download_dir = "downloads"
        os.makedirs(self.download_dir, exist_ok=True)
        self.max_workers = 5  # 最大线程数
        self.lock = threading.Lock()  # 文件写入锁

    def download(self, novel_name, source, progress_callback):
        try:
            if source == "起点中文网":
                return self.download_qidian(novel_name, progress_callback)
            elif source == "晋江文学城":
                return self.download_jjwxc(novel_name, progress_callback)
            else:
                return self.mock_download(novel_name, progress_callback)
        except Exception as e:
            print(f"下载出错: {e}")
            return False

    def download_qidian(self, novel_name, progress_callback):
        chapters = self.get_qidian_chapters(novel_name)
        if not chapters:
            return False

        file_path = os.path.join(self.download_dir, f"{novel_name}.txt")

        # 创建文件并写入标题
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"《{novel_name}》\n\n")

        total = len(chapters)
        completed = 0

        # 使用线程池下载章节
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for idx, (chapter_title, chapter_url) in enumerate(chapters):
                future = executor.submit(
                    self.download_chapter,
                    chapter_title,
                    chapter_url,
                    file_path,
                    idx
                )
                futures[future] = (chapter_title, idx)

            # 监控下载进度
            for future in as_completed(futures):
                chapter_title, idx = futures[future]
                try:
                    success = future.result()
                    if success:
                        completed += 1
                        progress = int(completed / total * 100)
                        progress_callback(novel_name, progress)
                except Exception as e:
                    print(f"下载章节出错: {e}")

        return True

    def download_jjwxc(self, novel_name, progress_callback):
        chapters = self.get_jjwxc_chapters(novel_name)
        if not chapters:
            return False

        file_path = os.path.join(self.download_dir, f"{novel_name}.txt")

        # 创建文件并写入标题
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"《{novel_name}》\n\n")

        total = len(chapters)
        completed = 0

        # 使用线程池下载章节
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for idx, (chapter_title, chapter_url) in enumerate(chapters):
                future = executor.submit(
                    self.download_chapter,
                    chapter_title,
                    chapter_url,
                    file_path,
                    idx
                )
                futures[future] = (chapter_title, idx)

            # 监控下载进度
            for future in as_completed(futures):
                chapter_title, idx = futures[future]
                try:
                    success = future.result()
                    if success:
                        completed += 1
                        progress = int(completed / total * 100)
                        progress_callback(novel_name, progress)
                except Exception as e:
                    print(f"下载章节出错: {e}")

        return True

    def download_chapter(self, chapter_title, chapter_url, file_path, idx):
        """下载单个章节（多线程调用）"""
        try:
            content = self.get_chapter_content(chapter_url)

            # 使用锁确保线程安全的文件写入
            with self.lock:
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.write(f"\n\n{chapter_title}\n\n")
                    f.write(content)

            return True
        except Exception as e:
            print(f"下载章节 {chapter_title} 出错: {e}")
            return False

    def get_qidian_chapters(self, novel_name):
        """获取起点小说章节列表（模拟）"""
        return [
            (f"第{i + 1}章 章节标题{i + 1}", f"https://www.qidian.com/chapter/{i + 1}")
            for i in range(50)  # 模拟50章
        ]

    def get_jjwxc_chapters(self, novel_name):
        """获取晋江小说章节列表（模拟）"""
        return [
            (f"第{i + 1}章 章节标题{i + 1}", f"https://www.jjwxc.net/chapter/{i + 1}")
            for i in range(40)  # 模拟40章
        ]

    def get_chapter_content(self, chapter_url):
        """获取章节内容（模拟）"""
        try:
            # 模拟不同章节的随机延迟
            time.sleep(random.uniform(0.1, 0.5))
            return f"这里是章节内容。\n" * random.randint(10, 30)
        except:
            return "章节内容获取失败"

    def mock_download(self, novel_name, progress_callback):
        """模拟下载过程"""
        try:
            file_path = os.path.join(self.download_dir, f"{novel_name}.txt")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"《{novel_name}》\n\n")

                # 模拟下载过程
                for i in range(1, 11):
                    time.sleep(0.3)
                    progress = i * 10
                    progress_callback(novel_name, progress)
                    f.write(f"\n\n第{i}章 章节标题{i}\n\n")
                    f.write(f"这里是章节{i}的内容。" * 20 + "\n")

            return True
        except Exception as e:
            print(f"模拟下载出错: {e}")
            return False