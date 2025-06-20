from lib2to3.pytree import convert

import requests
from bs4 import BeautifulSoup
import random
import time
import re
import json
from urllib.parse import quote, urlparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


class SearchEngine:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0',
            'Cookie': 'e1=%7B%22l6%22%3A%22%22%2C%22l7%22%3A%22%22%2C%22l1%22%3A3%2C%22l3%22%3A%22%22%2C%22pid%22%3A%22qd_P_Searchresult%22%2C%22eid%22%3A%22qd_S81%22%7D; e2=%7B%22l6%22%3A%22%22%2C%22l7%22%3A%22%22%2C%22l1%22%3A3%2C%22l3%22%3A%22%22%2C%22pid%22%3A%22qd_P_Searchresult%22%2C%22eid%22%3A%22qd_S81%22%7D; newstatisticUUID=1749714440_579532996; fu=1350508244; _gid=GA1.2.1857854848.1749714442; supportwebp=true; e1=%7B%22l6%22%3A%22%22%2C%22l7%22%3A%22%22%2C%22l1%22%3A9%2C%22l3%22%3A%22%22%2C%22pid%22%3A%22qd_p_qidian%22%2C%22eid%22%3A%22qd_A110%22%2C%22l2%22%3A2%7D; e2=%7B%22l6%22%3A%22%22%2C%22l7%22%3A%22%22%2C%22l1%22%3A%22%22%2C%22l3%22%3A%22%22%2C%22pid%22%3A%22qd_p_qidian%22%2C%22eid%22%3A%22%22%7D; _csrfToken=hMHzraPYL9sWaSwgMhtHuVhFBllja9pMIi1wZvMt; Hm_lvt_f00f67093ce2f38f215010b699629083=1749714441,1749727352; HMACCOUNT=1A2EB78DBCA3777F; supportWebp=true; traffic_utm_referer=https%3A%2F%2Fcn.bing.com%2F; traffic_search_engine=; se_ref=; Hm_lpvt_f00f67093ce2f38f215010b699629083=1749729896; _ga=GA1.2.1148801729.1749714442; _ga_FZMMH98S83=GS2.1.s1749727352$o2$g1$t1749730260$j52$l0$h0; _ga_PFYW0QLV3P=GS2.1.s1749727352$o2$g1$t1749730260$j52$l0$h0; w_tsfp=ltvuV0MF2utBvS0Q7aPul0usEDgkdzk4h0wpEaR0f5thQLErU5mB2IF5vsnxNHHX4sxnvd7DsZoyJTLYCJI3dwNGRsuVctpE31mQltJwj9xFAhBhE5vZCgIfd7hzuTYSdXhCNxS00jA8eIUd379yilkMsyN1zap3TO14fstJ019E6KDQmI5uDW3HlFWQRzaLbjcMcuqPr6g18L5a5TfU4A7/LFt1A+xAhBGS1SAYDXF2sxW9cuxYMhupJc6mSqA=',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        self.max_workers = 5  # 最大线程数

    def search(self, source, novel_name):
        """根据来源搜索小说"""
        try:
            if source == "起点中文网":
                return self.search_qidian(novel_name)
            elif source == "晋江文学城":
                return self.search_jjwxc(novel_name)
            else:
                return []
        except Exception as e:
            print(f"搜索出错: {e}")
            return []


    def search_qidian(self, novel_name):
        """搜索起点中文网"""
        search_url = f"https://www.qidian.com/so/{quote(novel_name)}.html"

        try:
            response = requests.get(search_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            book_items = soup.find_all('li', attrs={'class': 'res-book-item jsAutoReport'})

            # 使用线程池并行处理每个书籍的详细信息
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for item in book_items:
                    futures.append(executor.submit(self.process_qidian_item, item))

                results = []
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        results.append(result)

            return results

        except requests.RequestException as e:
            print(f"请求起点搜索出错: {e}")
            return []

    def process_qidian_item(self, item):
        """处理单个起点书籍项（多线程调用）"""
        book_id = '未知'
        title = '未知'
        author = '未知'
        status = '未知'
        chapter_num = '未知'

        try:
            author = item.find('div', attrs={'class': 'book-mid-info'}).find('p', attrs={'class': 'author'}).find('i').text
        except:
            try:
                author = item.find('div', attrs={'class': 'book-mid-info'}).find('a', attrs={'rel': 'nofollow'}).text
            except:
                pass
        try:
            title = item.find('div', attrs={'class': 'book-mid-info'}).find('h3',attrs={'class': 'book-info-title'}).find('a').text
            status = item.find('div', attrs={'class': 'book-mid-info'}).find('p', attrs={'class': 'author'}).find('span').text
            book_url = 'https:' + item.find('div', attrs={'class': 'book-mid-info'}).find('h3', attrs={'class': 'book-info-title'}).find('a')['href']
            book_id = self.extract_qidian_book_id(book_url)
            chapter_num = self.get_qidian_chapter_count(book_url)
        except:
            pass

        # 返回结果包含书籍ID
        return {
            "id": f"qidian_{book_id}",
            "title": title,
            "author": author,
            "source": "起点中文网",
            "status": status,
            "chapters": f"{chapter_num}章"
        }

    def extract_qidian_book_id(self, book_url):
        """从书籍URL中提取书籍ID"""
        try:
            # 示例URL: /info/1021617576
            path = urlparse(book_url).path
            book_id = path.split('/')[-2]
            return book_id
        except:
            return "unknown"

    def get_qidian_chapter_count(self, chapter_url):
        """获取起点章节数量（多线程调用）"""
        try:
            res = requests.get(chapter_url, headers=self.headers, timeout=10)
            s = BeautifulSoup(res.text, 'lxml')
            chapter_text = s.find('div', attrs={'class': 'catalog-header'}).find('span').text
            chapter_num = re.search(r'\d+', chapter_text).group()
            return chapter_num
        except:
            return "未知"

    def search_jjwxc(self, novel_name):
        """搜索晋江文学城"""
        name = self.convert_chinese_to_gbk_percent(novel_name)
        search_url = f"https://www.jjwxc.net/search.php?kw={quote(name)}&ord=&t=1"

        try:
            response = requests.get(search_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'lxml')
            book_items = soup.find('div', attrs={'id':'search_result'}).find_all('div', attrs={'class' : False, 'style' : False})
            # 使用线程池并行处理每个书籍的详细信息
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for item in book_items:
                    futures.append(executor.submit(self.process_jjwxc_item, item))

                results = []
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        results.append(result)

            return results

        except requests.RequestException as e:
            print(f"请求晋江搜索出错: {e}")
            return []

    def process_jjwxc_item(self, item):
        """处理单个晋江书籍项（多线程调用）"""
        title_elem = '未知'
        title = '未知'
        author = '未知'
        status = '未知'
        chapter = '未知'

        try:
            title_elem = item.find('h3',class_='title').find('a')
            title = title_elem.text.strip()
            author = item.find('div',class_='info').find('span').text.strip()
            book_url = title_elem['href']
            book_id = self.extract_jjwxc_book_id(book_url)
            chapter_num = self.get_jjwxc_chapter_count(book_url)

            try:
                status = item.find('div', class_='info').find('font').text.strip()
            except:
                status = '连载'

            return {
                "id": f"jjwxc_{book_id}",
                "title": title,
                "author": author,
                "source": "晋江文学城",
                "status": status,
                "chapters": chapter_num
            }
        except Exception as e:
            print(f"处理晋江书籍项出错: {e}")
            return None

    def extract_jjwxc_book_id(self, book_url):
        """从书籍URL中提取书籍ID"""
        try:
            # 示例URL: onebook.php?novelid=123456
            parsed = urlparse(book_url)
            # 解析查询参数获取novelid
            params = dict(param.split('=') for param in parsed.query.split('&'))
            return params.get('novelid', 'unknown')
        except:
            return "unknown"

    def get_jjwxc_chapter_count(self, chapter_url):
        """获取起点章节数量（多线程调用）"""
        try:
            res = requests.get(chapter_url, headers=self.headers, timeout=10)
            res.encoding = res.apparent_encoding
            s = BeautifulSoup(res.text, 'lxml')
            chapter_num = len(s.find_all('tr', attrs={'itemprop': 'chapter'}))
            return chapter_num
        except:
            return "未知"

    def convert_chinese_to_gbk_percent(self,s):
        result = []
        for char in s:
            # 判断是否为汉字（Unicode范围：\u4e00-\u9fff）
            if '\u4e00' <= char <= '\u9fff':
                # 转换为GBK编码的字节序列
                gbk_bytes = char.encode('gbk')
                # 每个字节格式化为%XX的大写形式
                for byte in gbk_bytes:
                    result.append(f"%{byte:02X}")
            else:
                result.append(char)
        return ''.join(result)