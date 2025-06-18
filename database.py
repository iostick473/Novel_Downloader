import sqlite3
import os
import json
import time
import hashlib
from datetime import datetime
import platform
from pathlib import Path
import threading
import datetime as dt  # 添加别名避免冲突


class NovelDatabase:
    def __init__(self, db_path=None):
        # 添加线程锁
        self.lock = threading.Lock()

        # 确保应用数据目录存在
        app_data_dir = self.get_app_data_dir()
        app_data_dir.mkdir(parents=True, exist_ok=True)  # 确保目录存在

        # 如果提供了自定义路径，直接使用
        if db_path:
            # 确保目录存在
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            self.db_path = db_path
            self.init_database()
            return

        # 获取应用数据目录
        app_data_dir = self.get_app_data_dir()

        # 尝试从配置文件读取数据库路径
        config_path = app_data_dir / "config.json"
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    custom_db_folder = config.get("database_folder")
                    if custom_db_folder and os.path.isabs(custom_db_folder):
                        # 确保目录存在
                        os.makedirs(custom_db_folder, exist_ok=True)
                        # 数据库文件路径
                        db_file_path = os.path.join(custom_db_folder, "novel_database.db")
                        self.db_path = db_file_path
                        self.init_database()
                        return
            except Exception as e:
                print(f"读取配置文件失败: {e}")

        # 使用默认数据库路径
        self.db_path = str(app_data_dir / "novel_database.db")
        # 确保目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_database()

    def get_app_data_dir(self):
        """获取跨平台的应用数据目录"""
        system = platform.system()
        if system == "Windows":
            app_data = Path(os.getenv('APPDATA'))
            return app_data / "NovelDownloader"
        elif system == "Darwin":  # macOS
            return Path.home() / "Library" / "Application Support" / "NovelDownloader"
        else:  # Linux and other Unix-like
            return Path.home() / ".novel_downloader"

    def init_database(self):
        """确保数据库目录存在并初始化数据库"""
        # 确保数据库目录存在
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        """初始化数据库和表结构"""
        try:
            # 使用connect创建数据库文件（如果不存在）
            conn = sqlite3.connect(self.db_path)

            # 启用WAL模式，提高并发性能
            conn.execute("PRAGMA journal_mode=WAL;")

            cursor = conn.cursor()

            # 创建书籍信息表
            cursor.execute('''
                 CREATE TABLE IF NOT EXISTS books (
                     id TEXT PRIMARY KEY,
                     source TEXT NOT NULL,
                     title TEXT NOT NULL,
                     author TEXT NOT NULL,
                     status TEXT,
                     chapters TEXT,
                     last_search TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                     search_count INTEGER DEFAULT 1,
                     metadata TEXT,
                     total_chapters INTEGER DEFAULT 0,
                     last_read_time TIMESTAMP
                 )
             ''')

            # 创建下载记录表
            cursor.execute('''
                 CREATE TABLE IF NOT EXISTS downloads (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     book_id TEXT NOT NULL,
                     download_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                     file_path TEXT NOT NULL,
                     file_size INTEGER,
                     download_status TEXT,
                     FOREIGN KEY (book_id) REFERENCES books(id)
                 )
             ''')

            # 创建阅读进度表
            cursor.execute('''
                 CREATE TABLE IF NOT EXISTS reading_progress (
                     book_id TEXT PRIMARY KEY,
                     current_chapter INTEGER DEFAULT 1,
                     chapter_position INTEGER DEFAULT 0,
                     last_read_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                     bookmarked BOOLEAN DEFAULT 0,
                     notes TEXT,
                     FOREIGN KEY (book_id) REFERENCES books(id)
                 )
             ''')

            # 创建分类表
            cursor.execute('''
                 CREATE TABLE IF NOT EXISTS categories (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     name TEXT UNIQUE NOT NULL,
                     color TEXT
                 )
             ''')

            # 创建书籍分类关系表
            cursor.execute('''
                 CREATE TABLE IF NOT EXISTS book_categories (
                     book_id TEXT NOT NULL,
                     category_id INTEGER NOT NULL,
                     PRIMARY KEY (book_id, category_id),
                     FOREIGN KEY (book_id) REFERENCES books(id),
                     FOREIGN KEY (category_id) REFERENCES categories(id)
                 )
             ''')

            # 创建阅读历史表
            cursor.execute('''
                 CREATE TABLE IF NOT EXISTS reading_history (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     book_id TEXT NOT NULL,
                     read_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                     duration INTEGER,
                     chapters_read INTEGER,
                     FOREIGN KEY (book_id) REFERENCES books(id)
                 )
             ''')

            # 创建默认分类
            default_categories = [
                ("已下载", "#4CAF50"),
                ("收藏", "#FFC107"),
                ("待读", "#2196F3"),
                ("已读", "#9C27B0"),
                ("连载中", "#F44336"),
                ("最近阅读", "#FF5722")
            ]

            for name, color in default_categories:
                try:
                    cursor.execute(
                        "INSERT OR IGNORE INTO categories (name, color) VALUES (?, ?)",
                        (name, color)
                    )
                except sqlite3.IntegrityError:
                    # 分类已存在
                    pass

            conn.commit()
        except Exception as e:
            print(f"数据库初始化失败: {e}")
            raise
        finally:
            if conn:
                conn.close()

        # 添加样例数据（只调用一次）
        self.create_sample_data()

    def get_all_books(self):
        """获取所有书籍"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM books")
            books = []
            for row in cursor.fetchall():
                book = dict(row)
                # 解析metadata
                if book.get('metadata'):
                    try:
                        metadata = json.loads(book['metadata'])
                        book.update(metadata)
                    except:
                        pass
                books.append(book)
            return books

    def get_book_downloads(self, book_id):
        """获取书籍的下载记录"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM downloads WHERE book_id = ?", (book_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_book(self, book_id):
        """获取单本书籍信息"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
            row = cursor.fetchone()
            if row:
                book = dict(row)
                # 解析metadata
                if book.get('metadata'):
                    try:
                        metadata = json.loads(book['metadata'])
                        book.update(metadata)
                    except:
                        pass
                return book
            return None

    def get_books_in_category(self, category_name):
        """获取指定分类下的所有书籍"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT b.* 
                FROM books b
                JOIN book_categories bc ON b.id = bc.book_id
                JOIN categories c ON bc.category_id = c.id
                WHERE c.name = ?
            ''', (category_name,))
            books = []
            for row in cursor.fetchall():
                book = dict(row)
                if book.get('metadata'):
                    try:
                        metadata = json.loads(book['metadata'])
                        book.update(metadata)
                    except:
                        pass
                books.append(book)
            return books

    def get_categories(self):
        """获取所有分类"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM categories")
            return [dict(row) for row in cursor.fetchall()]

    def get_book_categories(self, book_id):
        """获取书籍所属的分类"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.name 
                FROM categories c
                JOIN book_categories bc ON c.id = bc.category_id
                WHERE bc.book_id = ?
            ''', (book_id,))
            return [row[0] for row in cursor.fetchall()]

    def get_bookmarked_books(self):
        """获取所有带书签的书籍"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT b.*, rp.current_chapter, rp.chapter_position, rp.last_read_time
                FROM books b
                JOIN reading_progress rp ON b.id = rp.book_id
                WHERE rp.bookmarked = 1
            ''')
            books = []
            for row in cursor.fetchall():
                book = dict(row)
                if book.get('metadata'):
                    try:
                        metadata = json.loads(book['metadata'])
                        book.update(metadata)
                    except:
                        pass
                books.append(book)
            return books

    def create_sample_data(self):
        """创建样例数据"""
        # 检查是否已有数据
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM books")
            count = cursor.fetchone()[0]

            # 如果已有数据，不再添加样例
            if count > 0:
                return

        # 创建样例书籍
        sample_books = [
            {
                "id": "qidian_1021617576",
                "source": "起点中文网",
                "title": "诡秘之主",
                "author": "爱潜水的乌贼",
                "status": "已完结",
                "chapters": "1434章",
                "total_chapters": 1434,
                "last_read_time": dt.datetime.now().isoformat()  # 使用别名
            },
            {
                "id": "qidian_107580",
                "source": "起点中文网",
                "title": "斗破苍穹",
                "author": "天蚕土豆",
                "status": "已完结",
                "chapters": "1623章",
                "total_chapters": 1623,
                "last_read_time": datetime.datetime.now().isoformat()
            },
            {
                "id": "jjwxc_3663542",
                "source": "晋江文学城",
                "title": "镇魂",
                "author": "Priest",
                "status": "已完结",
                "chapters": "112章",
                "total_chapters": 112,
                "last_read_time": datetime.datetime.now().isoformat()
            },
            {
                "id": "jjwxc_3458185",
                "source": "晋江文学城",
                "title": "魔道祖师",
                "author": "墨香铜臭",
                "status": "已完结",
                "chapters": "126章",
                "total_chapters": 126,
                "last_read_time": datetime.datetime.now().isoformat()
            }
        ]

        # 创建样例下载记录
        sample_downloads = [
            {
                "book_id": "qidian_1021617576",
                "file_path": "downloads/诡秘之主.txt",
                "file_size": 1024000,
                "download_status": "completed"
            },
            {
                "book_id": "qidian_107580",
                "file_path": "downloads/斗破苍穹.txt",
                "file_size": 1500000,
                "download_status": "completed"
            },
            {
                "book_id": "jjwxc_3663542",
                "file_path": "downloads/镇魂.txt",
                "file_size": 512000,
                "download_status": "completed"
            },
            {
                "book_id": "jjwxc_3458185",
                "file_path": "downloads/魔道祖师.txt",
                "file_size": 600000,
                "download_status": "completed"
            }
        ]

        # 创建样例阅读进度
        sample_progress = [
            {
                "book_id": "qidian_1021617576",
                "current_chapter": 250,
                "chapter_position": 0.35,
                "bookmarked": 1,
                "notes": "非常精彩的世界观设定"
            },
            {
                "book_id": "qidian_107580",
                "current_chapter": 1200,
                "chapter_position": 0.75,
                "bookmarked": 0,
                "notes": "经典玄幻小说"
            },
            {
                "book_id": "jjwxc_3663542",
                "current_chapter": 80,
                "chapter_position": 0.15,
                "bookmarked": 1,
                "notes": "人物塑造深刻"
            }
        ]

        # 创建样例阅读历史
        sample_history = [
            {
                "book_id": "qidian_1021617576",
                "duration": 3600,  # 1小时
                "chapters_read": 5
            },
            {
                "book_id": "qidian_107580",
                "duration": 1800,  # 30分钟
                "chapters_read": 3
            }
        ]

        # 使用线程锁确保安全插入数据
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 插入书籍数据
                for book in sample_books:
                    # 将额外信息保存到metadata字段
                    metadata = {
                        'source': book.get('source', ''),
                        'additional': {k: v for k, v in book.items() if k not in [
                            'id', 'title', 'author', 'status', 'chapters', 'source'
                        ]}
                    }

                    cursor.execute('''
                        INSERT OR IGNORE INTO books 
                        (id, source, title, author, status, chapters, metadata, total_chapters, last_read_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        book['id'],
                        book['source'],
                        book['title'],
                        book['author'],
                        book['status'],
                        book['chapters'],
                        json.dumps(metadata),
                        book.get('total_chapters', 0),
                        book.get('last_read_time', datetime.datetime.now().isoformat())
                    ))

                # 插入下载记录
                for download in sample_downloads:
                    cursor.execute('''
                        INSERT OR IGNORE INTO downloads 
                        (book_id, file_path, file_size, download_status)
                        VALUES (?, ?, ?, ?)
                    ''', (
                        download['book_id'],
                        download['file_path'],
                        download['file_size'],
                        download['download_status']
                    ))

                # 插入阅读进度
                for progress in sample_progress:
                    cursor.execute('''
                        INSERT OR REPLACE INTO reading_progress 
                        (book_id, current_chapter, chapter_position, bookmarked, notes)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        progress['book_id'],
                        progress['current_chapter'],
                        progress['chapter_position'],
                        progress['bookmarked'],
                        progress['notes']
                    ))

                # 插入阅读历史
                for history in sample_history:
                    cursor.execute('''
                        INSERT OR IGNORE INTO reading_history 
                        (book_id, duration, chapters_read)
                        VALUES (?, ?, ?)
                    ''', (
                        history['book_id'],
                        history['duration'],
                        history['chapters_read']
                    ))

                # 添加书籍到分类
                # 所有书籍添加到"已下载"分类
                for book in sample_books:
                    self._add_book_to_category(book['id'], "已下载", cursor)

                # 添加书签书籍到"收藏"分类
                for progress in sample_progress:
                    if progress['bookmarked']:
                        self._add_book_to_category(progress['book_id'], "收藏", cursor)

                # 添加最近阅读书籍到"最近阅读"分类
                self._add_book_to_category("qidian_1021617576", "最近阅读", cursor)
                self._add_book_to_category("qidian_107580", "最近阅读", cursor)

                conn.commit()

    def save_book(self, book_info):
        """保存或更新书籍信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 检查书籍是否已存在
            cursor.execute("SELECT id FROM books WHERE id = ?", (book_info['id'],))
            existing = cursor.fetchone()

            if existing:
                # 更新现有记录
                cursor.execute('''
                    UPDATE books 
                    SET title = ?, author = ?, status = ?, chapters = ?, 
                        last_search = CURRENT_TIMESTAMP, search_count = search_count + 1
                    WHERE id = ?
                ''', (
                    book_info['title'],
                    book_info['author'],
                    book_info['status'],
                    book_info['chapters'],
                    book_info['id']
                ))
            else:
                # 插入新记录
                # 将额外信息保存到metadata字段
                metadata = {
                    'source': book_info.get('source', ''),
                    'additional': {k: v for k, v in book_info.items() if k not in [
                        'id', 'title', 'author', 'status', 'chapters', 'source'
                    ]}
                }

                cursor.execute('''
                    INSERT INTO books (id, source, title, author, status, chapters, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    book_info['id'],
                    book_info.get('source', '未知来源'),
                    book_info['title'],
                    book_info['author'],
                    book_info['status'],
                    book_info['chapters'],
                    json.dumps(metadata)
                ))

            conn.commit()

    def set_custom_db_path(self, new_folder):
        """设置自定义数据库文件夹路径并保存到配置文件"""
        # 确保目录存在
        os.makedirs(new_folder, exist_ok=True)

        # 数据库文件路径为：新文件夹 + 默认文件名
        db_file_path = os.path.join(new_folder, "novel_database.db")

        # 更新当前路径
        self.db_path = db_file_path

        # 保存到配置文件
        app_data_dir = self.get_app_data_dir()
        config_path = app_data_dir / "config.json"

        config = {}
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass

        config["database_folder"] = new_folder  # 存储文件夹路径

        # 确保配置目录存在
        app_data_dir.mkdir(parents=True, exist_ok=True)

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        # 重新初始化数据库
        self.init_database()

    def record_download(self, book_id, file_path, status="completed"):
        """记录下载信息 - 使用线程锁确保安全"""
        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            file_size = 0

        # 使用线程锁确保数据库访问安全
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO downloads (book_id, file_path, file_size, download_status)
                        VALUES (?, ?, ?, ?)
                    ''', (book_id, file_path, file_size, status))

                    # 如果下载成功，添加到"已下载"分类
                    if status == "completed":
                        # 使用内部方法避免递归锁
                        self._add_book_to_category(book_id, "已下载", cursor)

                    conn.commit()
            except sqlite3.OperationalError as e:
                print(f"数据库操作错误: {e}")
                # 重试机制
                time.sleep(0.1)
                self.record_download(book_id, file_path, status)
            except Exception as e:
                print(f"记录下载信息失败: {e}")

    def record_reading_time(self, book_id, reading_time, current_chapter):
        """记录阅读时间到数据库 - 简化实现"""
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()

                    # 创建阅读历史表（如果不存在）
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS reading_history (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            book_id TEXT NOT NULL,
                            reading_time REAL NOT NULL,
                            current_chapter INTEGER NOT NULL,
                            read_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (book_id) REFERENCES books(id)
                        )
                    ''')

                    # 插入阅读记录
                    cursor.execute('''
                        INSERT INTO reading_history (book_id, reading_time, current_chapter)
                        VALUES (?, ?, ?)
                    ''', (book_id, reading_time, current_chapter))

                    conn.commit()
        except Exception as e:
            print(f"记录阅读时间失败: {e}")

    def add_bookmark(self, book_id, chapter, position, note):
        """添加书签到数据库"""
        try:
            # 创建书签表（如果不存在）
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL,
                    chapter INTEGER NOT NULL,
                    position REAL NOT NULL,
                    note TEXT,
                    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (book_id) REFERENCES books(id)
                )
            ''')

            # 插入书签
            self.cursor.execute('''
                INSERT INTO bookmarks (book_id, chapter, position, note)
                VALUES (?, ?, ?, ?)
            ''', (book_id, chapter, position, note))

            self.conn.commit()
            return True
        except Exception as e:
            print(f"添加书签失败: {e}")
            return False

    # 新增：保存阅读进度
    def save_reading_progress(self, book_id, current_chapter, chapter_position, bookmarked=False, notes=''):
        """保存阅读进度，包括书签和笔记，并自动添加到最近阅读分类"""
        max_retries = 5
        retry_delay = 0.1  # 100毫秒

        for attempt in range(max_retries):
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    # 检查记录是否存在
                    cursor.execute("SELECT 1 FROM reading_progress WHERE book_id = ?", (book_id,))
                    exists = cursor.fetchone()

                    if exists:
                        # 更新现有记录
                        cursor.execute('''
                            UPDATE reading_progress 
                            SET current_chapter = ?, chapter_position = ?, last_read_time = ?, bookmarked = ?, notes = ?
                            WHERE book_id = ?
                        ''', (current_chapter, chapter_position, datetime.now(), bookmarked, notes, book_id))
                    else:
                        # 插入新记录
                        cursor.execute('''
                            INSERT INTO reading_progress (book_id, current_chapter, chapter_position, last_read_time, bookmarked, notes)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (book_id, current_chapter, chapter_position, datetime.now(), bookmarked, notes))

                    conn.commit()

                    # 同时将书籍添加到"最近阅读"分类
                    self.add_book_to_category(book_id, "最近阅读")
                    return True
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    # 如果是数据库锁定错误，等待后重试
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避策略
                else:
                    print(f"保存阅读进度失败: {e}")
                    return False
        return False

    # 新增：获取阅读进度
    def get_reading_progress(self, book_id):
        """获取阅读进度"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reading_progress WHERE book_id = ?", (book_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # 新增：添加阅读历史记录
    def add_reading_history(self, book_id, duration, chapters_read):
        """添加阅读历史记录"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO reading_history 
                (book_id, duration, chapters_read) 
                VALUES (?, ?, ?)
            ''', (book_id, duration, chapters_read))
            conn.commit()

    # 新增：获取最近阅读的书籍
    def get_recently_read_books(self, limit=10):
        """获取最近阅读的书籍（按最后阅读时间排序）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT b.*, rp.current_chapter, rp.chapter_position, rp.last_read_time
                FROM books b
                JOIN reading_progress rp ON b.id = rp.book_id
                ORDER BY rp.last_read_time DESC
                LIMIT ?
            ''', (limit,))

            books = []
            for row in cursor.fetchall():
                book = dict(row)
                # 解析metadata
                if book.get('metadata'):
                    metadata = json.loads(book['metadata'])
                    book.update(metadata)
                    del book['metadata']
                books.append(book)

            return books

    # 新增：获取阅读历史
    def get_reading_history(self, book_id, limit=20):
        """获取书籍的阅读历史"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM reading_history 
                WHERE book_id = ?
                ORDER BY read_time DESC
                LIMIT ?
            ''', (book_id, limit))

            return [dict(row) for row in cursor.fetchall()]

    # 新增：设置书签
    def toggle_bookmark(self, book_id):
        """切换书签状态"""
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()

                    # 检查书签状态
                    cursor.execute("SELECT bookmarked FROM reading_progress WHERE book_id=?", (book_id,))
                    row = cursor.fetchone()

                    if row:
                        # 切换书签状态
                        new_value = 0 if row[0] else 1
                        cursor.execute("UPDATE reading_progress SET bookmarked=? WHERE book_id=?", (new_value, book_id))
                    else:
                        # 创建新记录
                        cursor.execute("""
                            INSERT INTO reading_progress (book_id, bookmarked) 
                            VALUES (?, 1)
                        """, (book_id,))

                    conn.commit()
                    return new_value if row else 1
            except Exception as e:
                print(f"切换书签失败: {e}")
                return None

    # 新增：获取所有带书签的书籍
    def get_bookmarked_books(self):
        """获取所有带书签的书籍"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT b.*, rp.current_chapter, rp.chapter_position, rp.last_read_time
                FROM books b
                JOIN reading_progress rp ON b.id = rp.book_id
                WHERE rp.bookmarked = 1
                ORDER BY rp.last_read_time DESC
            ''')

            books = []
            for row in cursor.fetchall():
                book = dict(row)
                # 解析metadata
                if book.get('metadata'):
                    metadata = json.loads(book['metadata'])
                    book.update(metadata)
                    del book['metadata']
                books.append(book)

            return books

    def _add_book_to_category(self, book_id, category_name, cursor=None):
        """内部方法 - 将书籍添加到分类"""
        try:
            if cursor is None:
                # 如果没有提供游标，创建新的连接
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    self._add_book_to_category_internal(book_id, category_name, cursor)
                    conn.commit()
            else:
                # 使用提供的游标
                self._add_book_to_category_internal(book_id, category_name, cursor)
        except Exception as e:
            print(f"添加书籍到分类失败: {e}")

    def _add_book_to_category_internal(self, book_id, category_name, cursor):
        """内部方法 - 实际执行添加分类操作"""
        try:
            # 获取分类ID
            cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
            category = cursor.fetchone()

            if not category:
                # 如果分类不存在，创建它
                cursor.execute(
                    "INSERT INTO categories (name) VALUES (?)",
                    (category_name,)
                )
                category_id = cursor.lastrowid
            else:
                category_id = category[0]

            # 添加关系
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO book_categories (book_id, category_id) VALUES (?, ?)",
                    (book_id, category_id)
                )
            except sqlite3.IntegrityError:
                # 关系已存在
                pass
        except Exception as e:
            print(f"添加书籍到分类失败: {e}")

    def add_book_to_category(self, book_id, category_name):
        """将书籍添加到指定分类，如果分类不存在则创建"""
        max_retries = 5
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    # 获取分类ID
                    cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
                    category_row = cursor.fetchone()

                    if category_row:
                        category_id = category_row[0]
                    else:
                        # 创建新分类
                        cursor.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
                        category_id = cursor.lastrowid

                    # 检查是否已经存在关联
                    cursor.execute(
                        "SELECT 1 FROM book_categories WHERE book_id = ? AND category_id = ?",
                        (book_id, category_id)
                    )
                    exists = cursor.fetchone()

                    if not exists:
                        cursor.execute(
                            "INSERT INTO book_categories (book_id, category_id) VALUES (?, ?)",
                            (book_id, category_id)
                        )
                    conn.commit()
                    return True
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    print(f"添加书籍到分类失败: {e}")
                    return False
        return False

    def remove_book_from_category(self, book_id, category_name):
        """从分类中移除书籍"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 获取分类ID
            cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
            category = cursor.fetchone()

            if category:
                category_id = category[0]
                cursor.execute(
                    "DELETE FROM book_categories WHERE book_id = ? AND category_id = ?",
                    (book_id, category_id)
                )

            conn.commit()

    def get_book(self, book_id):
        """获取书籍信息"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM books WHERE id = ?", (book_id,))
            row = cursor.fetchone()

            if row:
                book = dict(row)
                # 解析metadata
                if book.get('metadata'):
                    metadata = json.loads(book['metadata'])
                    book.update(metadata)
                    del book['metadata']
                return book
            return None

    def get_all_books(self):
        """获取所有书籍信息"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM books ORDER BY last_search DESC")

            books = []
            for row in cursor.fetchall():
                book = dict(row)
                # 解析metadata
                if book.get('metadata'):
                    metadata = json.loads(book['metadata'])
                    book.update(metadata)
                    del book['metadata']
                books.append(book)

            return books

    def get_book_downloads(self, book_id):
        """获取书籍的下载记录"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM downloads 
                WHERE book_id = ?
                ORDER BY download_time DESC
            """, (book_id,))

            return [dict(row) for row in cursor.fetchall()]

    def get_categories(self):
        """获取所有分类"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM categories")
            return [dict(row) for row in cursor.fetchall()]

    def get_books_in_category(self, category_name):
        """获取分类中的书籍"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT b.* 
                FROM books b
                JOIN book_categories bc ON b.id = bc.book_id
                JOIN categories c ON bc.category_id = c.id
                WHERE c.name = ?
            """, (category_name,))

            books = []
            for row in cursor.fetchall():
                book = dict(row)
                # 解析metadata
                if book.get('metadata'):
                    metadata = json.loads(book['metadata'])
                    book.update(metadata)
                    del book['metadata']
                books.append(book)

            return books

    def get_book_categories(self, book_id):
        """获取书籍所属的分类"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.name 
                FROM categories c
                JOIN book_categories bc ON c.id = bc.category_id
                WHERE bc.book_id = ?
            """, (book_id,))

            return [row[0] for row in cursor.fetchall()]

    def search_books(self, keyword):
        """搜索书籍"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 使用SQLite的全文搜索功能 (FTS5)
            # 首先确保虚拟表存在
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS books_fts 
                USING fts5(id, title, author, content='books', content_rowid='rowid')
            """)

            # 如果虚拟表为空，填充数据
            cursor.execute("SELECT COUNT(*) FROM books_fts")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO books_fts (rowid, id, title, author)
                    SELECT rowid, id, title, author FROM books
                """)

            # 执行搜索
            cursor.execute("""
                SELECT b.* 
                FROM books b
                JOIN books_fts fts ON b.rowid = fts.rowid
                WHERE books_fts MATCH ?
                ORDER BY rank
            """, (f'"{keyword}"',))

            books = []
            for row in cursor.fetchall():
                book = dict(row)
                # 解析metadata
                if book.get('metadata'):
                    metadata = json.loads(book['metadata'])
                    book.update(metadata)
                    del book['metadata']
                books.append(book)

            return books

    def get_recent_searches(self, limit=10):
        """获取最近搜索的书籍"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM books 
                ORDER BY last_search DESC 
                LIMIT ?
            """, (limit,))

            books = []
            for row in cursor.fetchall():
                book = dict(row)
                # 解析metadata
                if book.get('metadata'):
                    metadata = json.loads(book['metadata'])
                    book.update(metadata)
                    del book['metadata']
                books.append(book)

            return books

    def get_most_searched(self, limit=10):
        """获取搜索次数最多的书籍"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM books 
                ORDER BY search_count DESC 
                LIMIT ?
            """, (limit,))

            books = []
            for row in cursor.fetchall():
                book = dict(row)
                # 解析metadata
                if book.get('metadata'):
                    metadata = json.loads(book['metadata'])
                    book.update(metadata)
                    del book['metadata']
                books.append(book)

            return books

    def delete_book(self, book_id):
        """删除书籍及其相关记录"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 删除下载记录
            cursor.execute("DELETE FROM downloads WHERE book_id = ?", (book_id,))

            # 删除分类关系
            cursor.execute("DELETE FROM book_categories WHERE book_id = ?", (book_id,))

            # 删除阅读进度
            cursor.execute("DELETE FROM reading_progress WHERE book_id = ?", (book_id,))

            # 删除阅读历史
            cursor.execute("DELETE FROM reading_history WHERE book_id = ?", (book_id,))

            # 删除书籍
            cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))

            # 删除全文搜索索引
            cursor.execute("""
                DELETE FROM books_fts 
                WHERE rowid IN (SELECT rowid FROM books WHERE id = ?)
            """, (book_id,))

            conn.commit()

    def export_library(self, export_path):
        """导出整个数据库到文件"""
        try:
            # 创建导出目录
            os.makedirs(export_path, exist_ok=True)

            # 1. 导出数据库文件
            db_export_path = os.path.join(export_path, "novel_library.db")
            with sqlite3.connect(self.db_path) as src, sqlite3.connect(db_export_path) as dest:
                src.backup(dest)

            # 2. 导出元数据
            metadata = {
                "export_time": datetime.datetime.now().isoformat(),
                "book_count": len(self.get_all_books()),
                "download_count": len(self.get_all_downloads()),
                "categories": self.get_categories()
            }

            metadata_path = os.path.join(export_path, "metadata.json")
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            # 3. 导出下载的小说文件
            downloads_dir = os.path.join(export_path, "downloads")
            os.makedirs(downloads_dir, exist_ok=True)

            all_downloads = self.get_all_downloads()
            for download in all_downloads:
                if os.path.exists(download['file_path']):
                    dest_path = os.path.join(downloads_dir, os.path.basename(download['file_path']))
                    # 复制文件
                    with open(download['file_path'], 'rb') as src, open(dest_path, 'wb') as dest:
                        dest.write(src.read())

            # 4. 导出阅读进度
            progress_data = {
                "progress": [],
                "history": []
            }

            # 获取所有阅读进度
            books = self.get_all_books()
            for book in books:
                progress = self.get_reading_progress(book['id'])
                if progress:
                    progress_data["progress"].append({
                        "book_id": book['id'],
                        "title": book['title'],
                        "current_chapter": progress['current_chapter'],
                        "chapter_position": progress['chapter_position'],
                        "last_read_time": progress['last_read_time'],
                        "notes": progress.get('notes', '')
                    })

                # 获取阅读历史
                history = self.get_reading_history(book['id'])
                if history:
                    progress_data["history"].extend([
                        {
                            "book_id": book['id'],
                            "title": book['title'],
                            "read_time": h['read_time'],
                            "duration": h['duration'],
                            "chapters_read": h['chapters_read']
                        } for h in history
                    ])

            progress_path = os.path.join(export_path, "reading_progress.json")
            with open(progress_path, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2, default=str)

            return True
        except Exception as e:
            print(f"导出失败: {e}")
            return False

    def get_all_downloads(self):
        """获取所有下载记录"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM downloads ORDER BY download_time DESC")
            return [dict(row) for row in cursor.fetchall()]

    def cleanup_database(self):
        """清理数据库，删除无效记录"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 删除没有书籍对应的下载记录
            cursor.execute("""
                DELETE FROM downloads
                WHERE book_id NOT IN (SELECT id FROM books)
            """)

            # 删除没有书籍对应的分类关系
            cursor.execute("""
                DELETE FROM book_categories
                WHERE book_id NOT IN (SELECT id FROM books)
            """)

            # 删除没有书籍对应的阅读进度
            cursor.execute("""
                DELETE FROM reading_progress
                WHERE book_id NOT IN (SELECT id FROM books)
            """)

            # 删除没有书籍对应的阅读历史
            cursor.execute("""
                DELETE FROM reading_history
                WHERE book_id NOT IN (SELECT id FROM books)
            """)

            conn.commit()

    def calculate_file_hash(self, file_path):
        """计算文件的哈希值用于验证完整性"""
        if not os.path.exists(file_path):
            return None

        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(65536)  # 64KB chunks
                if not data:
                    break
                hasher.update(data)

        return hasher.hexdigest()

    def verify_downloads(self):
        """验证下载文件的完整性"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 获取所有下载记录
            cursor.execute("SELECT id, file_path FROM downloads")
            downloads = cursor.fetchall()

            for download_id, file_path in downloads:
                if not os.path.exists(file_path):
                    # 文件不存在，标记为丢失
                    cursor.execute(
                        "UPDATE downloads SET download_status = 'missing' WHERE id = ?",
                        (download_id,)
                    )
                else:
                    # 文件存在，计算哈希值（可选）
                    # 这里可以根据需要添加哈希验证逻辑
                    cursor.execute(
                        "UPDATE downloads SET download_status = 'verified' WHERE id = ?",
                        (download_id,)
                    )

            conn.commit()