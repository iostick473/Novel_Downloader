import time
import random


class SearchEngine:
    def search(self, source, novel_name):
        """根据来源搜索小说"""
        # 模拟搜索延迟
        time.sleep(1.5)

        # 根据来源调用不同的搜索函数
        if source == "起点中文网":
            return self.search_qidian(novel_name)
        elif source == "晋江文学城":
            return self.search_jjwxc(novel_name)
        else:
            return []

    def search_qidian(self, novel_name):
        """模拟起点中文网搜索功能"""
        # 这里应该是实际的爬虫代码，现在使用模拟数据
        time.sleep(0.5)  # 模拟网络延迟

        # 模拟起点搜索结果
        results = []
        for i in range(1, random.randint(3, 8)):
            status = random.choice(["连载中", "已完结"])
            chapters = random.randint(100, 1500)
            author = random.choice(["唐家三少", "我吃西红柿", "辰东", "天蚕土豆", "爱潜水的乌贼"])

            results.append((
                f"{novel_name}（起点版）{i}",
                author,
                "起点中文网",
                status,
                f"{chapters}章"
            ))
        return results

    def search_jjwxc(self, novel_name):
        """模拟晋江文学城搜索功能"""
        # 这里应该是实际的爬虫代码，现在使用模拟数据
        time.sleep(0.5)  # 模拟网络延迟

        # 模拟晋江搜索结果
        results = []
        for i in range(1, random.randint(3, 8)):
            status = random.choice(["连载中", "已完结"])
            chapters = random.randint(30, 300)
            author = random.choice(["Priest", "墨香铜臭", "淮上", "巫哲", "漫漫何其多"])

            results.append((
                f"{novel_name}（晋江版）{i}",
                author,
                "晋江文学城",
                status,
                f"{chapters}章"
            ))
        return results