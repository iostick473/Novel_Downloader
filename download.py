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
import logging
from collections import defaultdict

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Downloader:
    def __init__(self, db=None):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0',
            'Cookie': 'e1=%7B%22l6%22%3A%22%22%2C%22l7%22%3A%22%22%2C%22l1%22%3A3%2C%22l3%22%3A%22%22%2C%22pid%22%3A%22qd_P_Searchresult%22%2C%22eid%22%3A%22qd_S81%22%7D; e2=%7B%22l6%22%3A%22%22%2C%22l7%22%3A%22%22%2C%22l1%22%3A3%2C%22l3%22%3A%22%22%2C%22pid%22%3A%22qd_P_Searchresult%22%2C%22eid%22%3A%22qd_S81%22%7D; newstatisticUUID=1749714440_579532996; fu=1350508244; _gid=GA1.2.1857854848.1749714442; supportwebp=true; e1=%7B%22l6%22%3A%22%22%2C%22l7%22%3A%22%22%2C%22l1%22%3A9%2C%22l3%22%3A%22%22%2C%22pid%22%3A%22qd_p_qidian%22%2C%22eid%22%3A%22qd_A110%22%2C%22l2%22%3A2%7D; e2=%7B%22l6%22%3A%22%22%2C%22l7%22%3A%22%22%2C%22l1%22%3A%22%22%2C%22l3%22%3A%22%22%2C%22pid%22%3A%22qd_p_qidian%22%2C%22eid%22%3A%22%22%7D; _csrfToken=hMHzraPYL9sWaSwgMhtHuVhFBllja9pMIi1wZvMt; Hm_lvt_f00f67093ce2f38f215010b699629083=1749714441,1749727352; HMACCOUNT=1A2EB78DBCA3777F; supportWebp=true; traffic_utm_referer=https%3A%2F%2Fcn.bing.com%2F; traffic_search_engine=; se_ref=; Hm_lpvt_f00f67093ce2f38f215010b699629083=1749729896; _ga=GA1.2.1148801729.1749714442; _ga_FZMMH98S83=GS2.1.s1749727352$o2$g1$t1749730260$j52$l0$h0; _ga_PFYW0QLV3P=GS2.1.s1749727352$o2$g1$t1749730260$j52$l0$h0; w_tsfp=ltvuV0MF2utBvS0Q7aPul0usEDgkdzk4h0wpEaR0f5thQLErU5mB2IF5vsnxNHHX4sxnvd7DsZoyJTLYCJI3dwNGRsuVctpE31mQltJwj9xFAhBhE5vZCgIfd7hzuTYSdXhCNxS00jA8eIUd379yilkMsyN1zap3TO14fstJ019E6KDQmI5uDW3HlFWQRzaLbjcMcuqPr6g18L5a5TfU4A7/LFt1A+xAhBGS1SAYDXF2sxW9cuxYMhupJc6mSqA=',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        self.download_dir = "downloads"
        os.makedirs(self.download_dir, exist_ok=True)
        self.max_workers = 5  # 最大线程数
        self.lock = threading.Lock()  # 文件写入锁
        self.db = db  # 数据库实例
        self.session = requests.Session()  # 使用会话保持连接
        self.session.headers.update(self.headers)
        self.chapter_cache = defaultdict(dict)  # 章节缓存 {novel_id: {index: (title, content)}}

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
                return []
        except Exception as e:
            logger.error(f"下载出错: {e}")
            return False

    def _common_download(self, novel_id, source, get_info_func, get_chapters_func, progress_callback):
        """通用下载逻辑"""
        # 提取实际书籍ID - 移除来源前缀
        if "_" in novel_id:
            book_id = novel_id.split("_", 1)[1]
        else:
            book_id = novel_id
        logger.info(f"提取书籍ID: {book_id} (原始ID: {novel_id})")

        # 获取小说信息
        novel_info = get_info_func(book_id)
        if not novel_info:
            return False

        novel_title = novel_info.get("title", f"{source}小说_{book_id}")
        file_path = os.path.join(self.download_dir, f"{novel_title}.txt")

        # 创建文件并写入标题
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"《{novel_title}》\n\n")
            f.write(f"作者: {novel_info.get('author', '未知')}\n")
            f.write(f"来源: {source}\n")
            f.write(f"状态: {novel_info.get('status', '未知')}\n\n")

        # 获取章节列表
        chapters = get_chapters_func(book_id)
        if not chapters:
            return False

        total = len(chapters)
        completed = 0

        # 清空章节缓存
        self.chapter_cache[novel_id] = {}

        # 使用线程池下载章节
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for idx, (chapter_title, chapter_url) in enumerate(chapters):
                future = executor.submit(
                    self.download_chapter_content,
                    novel_id,
                    chapter_title,
                    chapter_url,
                    idx
                )
                futures[future] = idx

            # 监控下载进度
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    success = future.result()
                    if success:
                        completed += 1
                        progress = int(completed / total * 100)
                        progress_callback(novel_id, progress)
                except Exception as e:
                    logger.error(f"下载章节出错: {e}")

        # 按顺序写入所有章节到文件
        self.write_chapters_to_file(novel_id, file_path, total, progress_callback)

        # 确保记录下载信息到数据库
        if self.db:
            self.db.record_download(novel_id, file_path)
            # 保存书籍基本信息
            book_info = {
                "id": novel_id,
                "title": novel_title,
                "author": novel_info.get('author', '未知'),
                "source": source,
                "status": novel_info.get('status', '未知'),
                "chapters": f"{len(chapters)}章"
            }
            self.db.save_book(book_info)

        # 清理缓存
        if novel_id in self.chapter_cache:
            del self.chapter_cache[novel_id]

        return True

    def write_chapters_to_file(self, novel_id, file_path, total_chapters, progress_callback):
        """按顺序写入所有章节到文件"""
        try:
            if novel_id not in self.chapter_cache:
                logger.warning(f"没有找到 {novel_id} 的章节缓存")
                return

            # 按索引顺序写入章节
            with open(file_path, 'a', encoding='utf-8') as f:
                for idx in range(total_chapters):
                    if idx in self.chapter_cache[novel_id]:
                        chapter_title, content = self.chapter_cache[novel_id][idx]
                        f.write(f"\n\n{chapter_title}\n\n")
                        f.write(content)
                        logger.info(f"已写入章节: {chapter_title}")
                    else:
                        logger.warning(f"缺失章节索引: {idx}")

                    # 更新写入进度
                    progress = int((idx + 1) / total_chapters * 100)
                    progress_callback(novel_id, progress)
        except Exception as e:
            logger.error(f"写入章节到文件失败: {e}")

    def download_qidian(self, novel_id, progress_callback):
        """根据小说ID下载起点小说"""
        return self._common_download(
            novel_id,
            "起点中文网",
            self.get_qidian_novel_info,
            self.get_qidian_chapters,
            progress_callback
        )

    def download_jjwxc(self, novel_id, progress_callback):
        """根据小说ID下载晋江小说"""
        return self._common_download(
            novel_id,
            "晋江文学城",
            self.get_jjwxc_novel_info,
            self.get_jjwxc_chapters,
            progress_callback
        )

    def get_qidian_novel_info(self, book_id):
        """获取起点小说基本信息"""
        try:
            # 确保book_id是纯数字
            if not book_id.isdigit():
                logger.error(f"无效的起点书籍ID: {book_id}")
                return None

            url = f"https://www.qidian.com/book/{book_id}/"
            logger.info(f"获取起点小说信息: {url}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')

            # 提取小说标题
            title_tag = soup.find('div', class_='book-info-top').find('h1')
            title = title_tag.get_text(strip=True) if title_tag else f"起点小说_{book_id}"

            # 提取作者
            author_tag = soup.find('a', class_='writer-name')
            author = author_tag.get_text(strip=True) if author_tag else "未知作者"

            # 提取状态
            status_tag = soup.find('p', class_='book-attribute').find('span')
            status = status_tag.get_text(strip=True) if status_tag else "状态未知"

            return {
                "title": title,
                "author": author,
                "status": status,
                "book_id": book_id
            }
        except Exception as e:
            logger.error(f"获取起点小说信息失败: {e}")
            return None

    def get_qidian_chapters(self, book_id):
        """获取起点小说章节列表"""
        try:
            # 确保book_id是纯数字
            if not book_id.isdigit():
                logger.error(f"无效的起点书籍ID: {book_id}")
                return None

            # 获取目录页URL
            catalog_url = f"https://www.qidian.com/book/{book_id}/"
            logger.info(f"获取起点章节列表: {catalog_url}")
            response = self.session.get(catalog_url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')

            # 查找所有卷
            volumes = soup.find_all('div', class_='catalog-volume')
            chapters = []

            for volume in volumes:

                # 检查是否是免费卷
                if volume.find('h3', class_='volume-name').get_text().find('免费') == -1:
                    continue

                # 获取章节列表
                chapter_list = volume.find('ul', class_='volume-chapters')
                if not chapter_list:
                    continue

                chapter_items = chapter_list.find_all('li')
                for item in chapter_items:
                    link = item.find('a')
                    if link and link.get('href'):
                        chapter_title = link.get_text(strip=True)
                        chapter_url = urljoin("https:", link['href'])
                        chapters.append((chapter_title, chapter_url))

            logger.info(f"找到 {len(chapters)} 个免费章节")
            return chapters
        except Exception as e:
            logger.error(f"获取起点章节列表失败: {e}")
            return None

    def download_chapter_content(self, novel_id, chapter_title, chapter_url, chapter_index):
        """下载单个章节内容并缓存"""
        try:
            # 随机延迟，避免被反爬
            time.sleep(random.uniform(0.5, 1.5))

            logger.info(f"下载章节: {chapter_title} ({chapter_url})")
            response = self.session.get(chapter_url, timeout=10)
            response.raise_for_status()

            # 从novel_id中提取来源
            source = novel_id.split("_")[0] if "_" in novel_id else "未知"

            # 根据来源选择不同的解析方式
            if source == "jjwxc":
                # 晋江文学城
                response.encoding = response.apparent_encoding
                soup = BeautifulSoup(response.text, 'lxml')
                content_div = soup.find('div', attrs={'class': 'novelbody'}).find('div')
                if not content_div:
                    logger.warning(f"未找到晋江章节内容: {chapter_title}")
                    return False

                # 清理不需要的元素
                for div in content_div.find_all('div'):
                    div.decompose()

                # 提取文本内容
                content = content_div.get_text().strip()
                # 移除多余空白和特定提示
                content = re.sub(r'\s+', '\n', content)

            elif source == 'qidian':
                # 起点中文网
                soup = BeautifulSoup(response.text, 'lxml')
                content_div = soup.find('main')
                if not content_div:
                    logger.warning(f"未找到章节内容: {chapter_title}")
                    return False
                content = content_div.get_text().strip()
                content = re.sub(r'\s+', '\n', content)

            else :
                pass
            # 缓存章节内容
            with self.lock:
                self.chapter_cache[novel_id][chapter_index] = (chapter_title, content)

            logger.info(f"已缓存章节: {chapter_title}")
            return True
        except Exception as e:
            logger.error(f"下载章节失败: {chapter_title} - {e}")
            return False

    def get_jjwxc_novel_info(self, book_id):
        try:
            # 确保book_id是纯数字
            if not book_id.isdigit():
                logger.error(f"无效的晋江文学城书籍ID: {book_id}")
                return None
            url = f"http://www.jjwxc.net/onebook.php?novelid={book_id}/"
            logger.info(f"获取晋江文学城小说信息: {url}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'lxml')
            # 提取小说标题
            title_tag = soup.find('span', attrs={'itemprop': 'articleSection'})
            title = title_tag.get_text(strip=True) if title_tag else f"晋江文学城小说_{book_id}"

            # 提取作者
            author_tag = soup.find('td', attrs={'colspan': '6'}).find('a', attrs={'href': True})
            author = author_tag.get_text(strip=True) if author_tag else "未知作者"

            # 提取状态
            status_tag = soup.find('div', attrs={'class': 'righttd'}).find('span', attrs={'style': 'color:#000;float:none','itemprop': 'updataStatus'})
            status = status_tag.get_text(strip=True) if status_tag else "状态未知"

            return {
                "title": title,
                "author": author,
                "status": status,
                "book_id": book_id
            }
        except Exception as e:
            logger.error(f"获取晋江文学城小说信息失败: {e}")
            return None

    def get_jjwxc_chapters(self, book_id):
        """获取晋江小说章节列表 """
        try:
            # 确保book_id是纯数字
            if not book_id.isdigit():
                logger.error(f"无效的晋江文学城书籍ID: {book_id}")
                return None
            url = f"http://www.jjwxc.net/onebook.php?novelid={book_id}/"
            logger.info(f"获取晋江文学城小说信息: {url}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'lxml')

            # 查找所有卷
            chapters = soup.find_all('tr', attrs={'itemprop': 'chapter'})
            free_chapters = []

            for chapter in chapters:
                # 检查是否是免费章
                if chapter.find('div', attrs={'style': 'float:left'}).get_text().find('VIP') == 1:
                    continue

                link = chapter.find('a',attrs={'itemprop': 'url'})
                if link and link.get('href'):
                    chapter_title = link.get_text(strip=True)+" "+chapter.find_all('td')[2].get_text(strip=True)
                    chapter_url = urljoin("https:", link['href'])
                    free_chapters.append((chapter_title, chapter_url))

            logger.info(f"找到 {len(free_chapters)} 个免费章节")
            return free_chapters
        except Exception as e:
            logger.error(f"获取晋江文学城章节列表失败: {e}")
            return None

    def get_download_info(self, novel_id):
        """获取下载信息"""
        # 这里返回一个包含文件路径和下载时间的字典列表
        # 实际实现应根据您的数据库结构进行调整
        return [{
            'file_path': os.path.join(self.download_dir, f"{novel_id}.txt"),
            'download_time': time.strftime("%Y-%m-%d %H:%M:%S")
        }]