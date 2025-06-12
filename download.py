import requests
import os
import time
import random
import re
from bs4 import BeautifulSoup
from urllib.parse import quote


class Downloader:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        self.download_dir = "downloads"
        os.makedirs(self.download_dir, exist_ok=True)

    def download(self, novel_name, source, progress_callback):
        """下载小说功能"""
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
        """下载起点中文网小说"""
        # 在实际应用中，这里需要获取小说的目录页URL
        # 我们使用模拟的章节列表
        chapters = self.get_qidian_chapters(novel_name)

        # 创建小说文件
        file_path = os.path.join(self.download_dir, f"{novel_name}.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"《{novel_name}》\n\n")

            # 下载每个章节
            total = len(chapters)
            for i, (chapter_title, chapter_url) in enumerate(chapters):
                # 更新进度
                progress = int((i + 1) / total * 100)
                progress_callback(novel_name, progress)

                # 获取章节内容
                content = self.get_chapter_content(chapter_url)

                # 写入文件
                f.write(f"\n\n{chapter_title}\n\n")
                f.write(content)

                # 添加延迟避免被封
                time.sleep(0.5)

        return True

    def download_jjwxc(self, novel_name, progress_callback):
        """下载晋江文学城小说"""
        # 在实际应用中，这里需要获取小说的目录页URL
        # 我们使用模拟的章节列表
        chapters = self.get_jjwxc_chapters(novel_name)

        # 创建小说文件
        file_path = os.path.join(self.download_dir, f"{novel_name}.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"《{novel_name}》\n\n")

            # 下载每个章节
            total = len(chapters)
            for i, (chapter_title, chapter_url) in enumerate(chapters):
                # 更新进度
                progress = int((i + 1) / total * 100)
                progress_callback(novel_name, progress)

                # 获取章节内容
                content = self.get_chapter_content(chapter_url)

                # 写入文件
                f.write(f"\n\n{chapter_title}\n\n")
                f.write(content)

                # 添加延迟避免被封
                time.sleep(0.5)

        return True

    def get_qidian_chapters(self, novel_name):
        """获取起点小说章节列表（模拟）"""
        # 在实际应用中，这里需要解析起点目录页
        return [
            (f"第{i + 1}章 章节标题{i + 1}", f"https://www.qidian.com/chapter/{i + 1}")
            for i in range(20)  # 模拟20章
        ]

    def get_jjwxc_chapters(self, novel_name):
        """获取晋江小说章节列表（模拟）"""
        # 在实际应用中，这里需要解析晋江目录页
        return [
            (f"第{i + 1}章 章节标题{i + 1}", f"https://www.jjwxc.net/chapter/{i + 1}")
            for i in range(15)  # 模拟15章
        ]

    def get_chapter_content(self, chapter_url):
        """获取章节内容（模拟）"""
        # 在实际应用中，这里需要请求章节URL并解析内容

        # 模拟请求章节内容
        try:
            # 实际代码示例:
            # response = requests.get(chapter_url, headers=self.headers, timeout=10)
            # soup = BeautifulSoup(response.text, 'html.parser')
            # content = soup.select_one('.chapter-content').text.strip()

            # 使用模拟内容
            return f"这里是章节内容。\n" * random.randint(10, 30)
        except:
            return "章节内容获取失败"

    def mock_download(self, novel_name, progress_callback):
        """模拟下载过程"""
        try:
            # 模拟下载过程
            for i in range(1, 11):
                time.sleep(0.3)
                progress = i * 10
                progress_callback(novel_name, progress)

            # 创建模拟文件
            file_path = os.path.join(self.download_dir, f"{novel_name}.txt")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"《{novel_name}》\n\n")
                for i in range(1, 21):
                    f.write(f"\n\n第{i}章 章节标题{i}\n\n")
                    f.write(f"这里是章节{i}的内容。" * 20 + "\n")

            return True

        except Exception as e:
            print(f"模拟下载出错: {e}")
            return False