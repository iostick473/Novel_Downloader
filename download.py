import time
import random


class Downloader:
    def download(self, novel_name, source, progress_callback):
        """下载小说功能"""
        try:
            # 模拟下载过程
            for i in range(1, 11):
                time.sleep(0.3)
                progress = i * 10
                progress_callback(novel_name, progress)

            # 模拟下载结果
            return random.choice([True, True, True, False])  # 75%成功率

        except Exception as e:
            print(f"下载出错: {e}")
            return False