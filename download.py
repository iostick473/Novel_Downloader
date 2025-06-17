import requests
import os
import time
import random
import re
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import sqlite3
import json


class Downloader:
    def __init__(self, db=None):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        self.download_dir = "downloads"
        os.makedirs(self.download_dir, exist_ok=True)
        self.max_workers = 5  # 最大线程数
        self.lock = threading.Lock()  # 文件写入锁
        self.db = db  # 数据库实例

    def set_database(self, db):
        """设置数据库实例"""
        self.db = db

    def download(self, novel_id, source, progress_callback):
        try:
            if source == "起点中文网":
                return self.download_qidian(novel_id, progress_callback)
            elif source == "晋江文学城":
                return self.download_jjwxc(novel_id, progress_callback)
            else:
                return self.mock_download(novel_id, progress_callback)
        except Exception as e:
            print(f"下载出错: {e}")
            return False

    def download_qidian(self, novel_id, progress_callback):
        """根据小说ID下载起点小说"""
        # 提取实际书籍ID
        if novel_id.startswith("qidian_"):
            book_id = novel_id.split("_")[1]
        else:
            book_id = novel_id

        # 获取小说信息
        novel_info = self.get_qidian_novel_info(book_id)
        if not novel_info:
            return False

        novel_title = novel_info.get("title", f"起点小说_{book_id}")

        # 获取章节列表
        chapters = self.get_qidian_chapters(book_id)
        if not chapters:
            return False

        file_path = os.path.join(self.download_dir, f"{novel_title}.txt")

        # 创建文件并写入标题
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"《{novel_title}》\n\n")
            f.write(f"作者: {novel_info.get('author', '未知')}\n")
            f.write(f"来源: 起点中文网\n")
            f.write(f"状态: {novel_info.get('status', '未知')}\n\n")

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
                        progress_callback(novel_id, progress)
                except Exception as e:
                    print(f"下载章节出错: {e}")

        # 确保记录下载信息到数据库
        if self.db:
            self.db.record_download(novel_id, file_path)
            # 保存书籍基本信息
            book_info = {
                "id": novel_id,
                "title": novel_title,
                "author": novel_info.get('author', '未知'),
                "source": "起点中文网",
                "status": novel_info.get('status', '未知'),
                "chapters": f"{len(chapters)}章"
            }
            self.db.save_book(book_info)

        return True

    def get_qidian_novel_info(self, book_id):
        """获取起点小说基本信息"""
        try:
            book_url = f"https://book.qidian.com/info/{book_id}"
            response = requests.get(book_url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')

            # 提取小说信息
            title = soup.find('div', class_='book-info').find('h1').find('em').text.strip()
            author = soup.find('div', class_='book-info').find('a', class_='writer').text.strip()
            status = soup.find('p', class_='tag').find_all('span')[1].text.strip()

            return {
                "title": title,
                "author": author,
                "status": status
            }
        except Exception as e:
            print(f"获取起点小说信息出错: {e}")
            return {
                "title": f"起点小说_{book_id}",
                "author": "未知",
                "status": "未知"
            }

    def download_jjwxc(self, novel_id, progress_callback):
        """根据小说ID下载晋江小说"""
        # 提取实际书籍ID
        if novel_id.startswith("jjwxc_"):
            book_id = novel_id.split("_")[1]
        else:
            book_id = novel_id

        # 获取小说信息
        novel_info = self.get_jjwxc_novel_info(book_id)
        if not novel_info:
            return False

        novel_title = novel_info.get("title", f"晋江小说_{book_id}")

        # 获取章节列表
        chapters = self.get_jjwxc_chapters(book_id)
        if not chapters:
            return False

        file_path = os.path.join(self.download_dir, f"{novel_title}.txt")

        # 创建文件并写入标题
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"《{novel_title}》\n\n")
            f.write(f"作者: {novel_info.get('author', '未知')}\n")
            f.write(f"来源: 晋江文学城\n")
            f.write(f"状态: {novel_info.get('status', '未知')}\n\n")

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
                        progress_callback(novel_id, progress)
                except Exception as e:
                    print(f"下载章节出错: {e}")

        # 确保记录下载信息到数据库
        if self.db:
            self.db.record_download(novel_id, file_path)
            # 保存书籍基本信息
            book_info = {
                "id": novel_id,
                "title": novel_title,
                "author": novel_info.get('author', '未知'),
                "source": "晋江文学城",
                "status": novel_info.get('status', '未知'),
                "chapters": f"{len(chapters)}章"
            }
            self.db.save_book(book_info)

        return True

    def get_jjwxc_novel_info(self, book_id):
        """获取晋江小说基本信息"""
        try:
            book_url = f"https://www.jjwxc.net/onebook.php?novelid={book_id}"
            response = requests.get(book_url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # 提取小说信息
            title = soup.find('span', itemprop='articleSection').text.strip()
            author = soup.find('span', itemprop='author').text.strip()
            status = soup.find('span', class_='red').text.strip()

            return {
                "title": title,
                "author": author,
                "status": status
            }
        except Exception as e:
            print(f"获取晋江小说信息出错: {e}")
            return {
                "title": f"晋江小说_{book_id}",
                "author": "未知",
                "status": "未知"
            }

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

    def get_qidian_chapters(self, book_id):
        """获取起点小说章节列表"""
        try:
            chapter_url = f"https://book.qidian.com/info/{book_id}/#Catalog"
            response = requests.get(chapter_url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')
            chapter_items = soup.find_all('li', attrs={'data-rid': re.compile(r'\d+')})

            chapters = []
            for item in chapter_items:
                try:
                    # 获取章节标题
                    title = item.find('a').text.strip()

                    # 获取章节URL
                    url = item.find('a')['href']
                    full_url = urljoin("https:", url)

                    chapters.append((title, full_url))
                except:
                    continue

            return chapters[:50]  # 限制前50章
        except Exception as e:
            print(f"获取起点章节列表出错: {e}")
            # 返回模拟数据
            return [
                (f"第{i + 1}章 章节标题{i + 1}", f"https://www.qidian.com/chapter/{book_id}/{i + 1}")
                for i in range(20)
            ]

    def get_jjwxc_chapters(self, book_id):
        """获取晋江小说章节列表"""
        try:
            chapter_url = f"https://www.jjwxc.net/onebook.php?novelid={book_id}"
            response = requests.get(chapter_url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            chapter_items = soup.select('div.chaptertitle a')

            chapters = []
            for item in chapter_items:
                try:
                    # 获取章节标题
                    title = item.text.strip()

                    # 获取章节URL
                    url = item['href']
                    full_url = urljoin("https://www.jjwxc.net/", url)

                    chapters.append((title, full_url))
                except:
                    continue

            return chapters[:40]  # 限制前40章
        except Exception as e:
            print(f"获取晋江章节列表出错: {e}")
            # 返回模拟数据
            return [
                (f"第{i + 1}章 章节标题{i + 1}", f"https://www.jjwxc.net/chapter/{book_id}/{i + 1}")
                for i in range(15)
            ]

    def get_chapter_content(self, chapter_url):
        """获取章节内容"""
        try:
            # 添加随机延迟
            time.sleep(random.uniform(0.1, 0.5))

            # 模拟不同章节的随机内容
            return f"这里是章节内容。\n" * random.randint(10, 30)
        except:
            return "章节内容获取失败"

    def mock_download(self, novel_id, progress_callback):
        """模拟下载过程"""
        try:
            # 从ID中提取书名
            if "_" in novel_id:
                novel_title = novel_id.split("_", 1)[1]
            else:
                novel_title = novel_id

            file_path = os.path.join(self.download_dir, f"{novel_title}.txt")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"《{novel_title}》\n\n")

                # 模拟下载过程
                for i in range(1, 11):
                    time.sleep(0.3)
                    progress = i * 10
                    progress_callback(novel_id, progress)
                    f.write(f"\n\n第{i}章 章节标题{i}\n\n")
                    f.write(f"这里是章节{i}的内容。" * 20 + "\n")

            # 确保记录下载信息到数据库
            if self.db:
                self.db.record_download(novel_id, file_path)
                # 保存书籍基本信息
                book_info = {
                    "id": novel_id,
                    "title": novel_title,
                    "author": "模拟作者",
                    "source": "模拟来源",
                    "status": "已完结",
                    "chapters": "10章"
                }
                self.db.save_book(book_info)

            return True
        except Exception as e:
            print(f"模拟下载出错: {e}")
            return False
