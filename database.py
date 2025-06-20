import sqlite3
import os
import json
import time
import hashlib
from datetime import datetime
import platform
from pathlib import Path
import threading


class NovelDatabase:
    def __init__(self, db_path=None):
        self.lock = threading.Lock()
        app_data_dir = self.get_app_data_dir()
        app_data_dir.mkdir(parents=True, exist_ok=True)

        if db_path:
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            self.db_path = db_path
        else:
            app_data_dir = self.get_app_data_dir()
            config_path = app_data_dir / "config.json"
            self.db_path = str(app_data_dir / "novel_database.db")

            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        if custom_db_folder := json.load(f).get("database_folder"):
                            if os.path.isabs(custom_db_folder):
                                os.makedirs(custom_db_folder, exist_ok=True)
                                self.db_path = os.path.join(custom_db_folder, "novel_database.db")
                except Exception as e:
                    print(f"读取配置文件失败: {e}")

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_database()

    def get_app_data_dir(self):
        system = platform.system()
        if system == "Windows":
            return Path(os.getenv('APPDATA')) / "NovelDownloader"
        elif system == "Darwin":
            return Path.home() / "Library" / "Application Support" / "NovelDownloader"
        return Path.home() / ".novel_downloader"

    def init_database(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                cursor = conn.cursor()

                # 创建核心表结构
                tables = [
                    '''CREATE TABLE IF NOT EXISTS books (
                        id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL,
                        author TEXT NOT NULL, status TEXT, chapters TEXT,
                        last_search TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        search_count INTEGER DEFAULT 1, metadata TEXT,
                        total_chapters INTEGER DEFAULT 0, last_read_time TIMESTAMP)''',
                    '''CREATE TABLE IF NOT EXISTS downloads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, book_id TEXT NOT NULL,
                        download_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        file_path TEXT NOT NULL, file_size INTEGER,
                        download_status TEXT, FOREIGN KEY (book_id) REFERENCES books(id))''',
                    '''CREATE TABLE IF NOT EXISTS reading_progress (
                        book_id TEXT PRIMARY KEY, current_chapter INTEGER DEFAULT 1,
                        chapter_position REAL DEFAULT 0, last_read_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        bookmarked BOOLEAN DEFAULT 0,
                        FOREIGN KEY (book_id) REFERENCES books(id))''',
                    '''CREATE TABLE IF NOT EXISTS categories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL, color TEXT)''',
                    '''CREATE TABLE IF NOT EXISTS book_categories (
                        book_id TEXT NOT NULL, category_id INTEGER NOT NULL,
                        PRIMARY KEY (book_id, category_id),
                        FOREIGN KEY (book_id) REFERENCES books(id),
                        FOREIGN KEY (category_id) REFERENCES categories(id))''',
                    '''CREATE TABLE IF NOT EXISTS reading_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, book_id TEXT NOT NULL,
                        read_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, duration REAL NOT NULL,
                        current_chapter INTEGER NOT NULL, chapters_read INTEGER,
                        FOREIGN KEY (book_id) REFERENCES books(id))''',
                    '''CREATE VIRTUAL TABLE IF NOT EXISTS books_fts 
                       USING fts5(id, title, author, content='books', content_rowid='rowid')'''
                ]

                for table in tables:
                    cursor.execute(table)

                # 创建默认分类
                for name, color in [
                    ("已下载", "#4CAF50"), ("收藏", "#FFC107"), ("最近阅读", "#FF5722")
                ]:
                    cursor.execute(
                        "INSERT OR IGNORE INTO categories (name, color) VALUES (?, ?)",
                        (name, color)
                    )
                conn.commit()
        except Exception as e:
            print(f"数据库初始化失败: {e}")
            raise

    def _row_to_book(self, row):
        """将数据库行转换为书籍字典并解析元数据"""
        book = dict(row)
        if metadata_str := book.pop('metadata', None):
            try:
                book.update(json.loads(metadata_str))
            except json.JSONDecodeError:
                pass
        return book

    def _execute_with_retry(self, operation, max_retries=5, base_delay=0.1):
        """带重试机制的数据库操作"""
        for attempt in range(max_retries):
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    return operation(cursor, conn)
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(base_delay * (2 ** attempt))
                else:
                    raise
        return None

    def _query_books(self, query, params=()):
        """通用书籍查询方法"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [self._row_to_book(dict(row)) for row in cursor.fetchall()]

    def get_book(self, book_id):
        """获取单本书籍信息"""
        books = self._query_books("SELECT * FROM books WHERE id = ?", (book_id,))
        return books[0] if books else None

    def get_all_books(self):
        """获取所有书籍"""
        return self._query_books("SELECT * FROM books")

    def get_books_in_category(self, category_name):
        """获取指定分类下的所有书籍"""
        return self._query_books('''
            SELECT b.* FROM books b
            JOIN book_categories bc ON b.id = bc.book_id
            JOIN categories c ON bc.category_id = c.id
            WHERE c.name = ?''', (category_name,))

    def get_bookmarked_books(self):
        """获取所有带书签的书籍"""
        return self._query_books('''
            SELECT b.*, rp.current_chapter, rp.chapter_position, rp.last_read_time
            FROM books b JOIN reading_progress rp ON b.id = rp.book_id
            WHERE rp.bookmarked = 1''')

    def get_recently_read_books(self, limit=10):
        """获取最近阅读的书籍"""
        return self._query_books('''
            SELECT b.*, rp.current_chapter, rp.chapter_position, rp.last_read_time
            FROM books b JOIN reading_progress rp ON b.id = rp.book_id
            ORDER BY rp.last_read_time DESC LIMIT ?''', (limit,))

    def save_book(self, book_info):
        """保存或更新书籍信息"""

        def operation(cursor, conn):
            # 准备元数据
            metadata = {
                'source': book_info.get('source', ''),
                'additional': {k: v for k, v in book_info.items() if k not in [
                    'id', 'title', 'author', 'status', 'chapters', 'source'
                ]}
            }
            metadata_str = json.dumps(metadata)

            if cursor.execute("SELECT id FROM books WHERE id = ?", (book_info['id'],)).fetchone():
                cursor.execute('''
                    UPDATE books SET title=?, author=?, status=?, chapters=?, 
                    last_search=CURRENT_TIMESTAMP, search_count=search_count+1
                    WHERE id=?''', (
                    book_info['title'], book_info['author'],
                    book_info['status'], book_info['chapters'], book_info['id']
                ))
            else:
                cursor.execute('''
                    INSERT INTO books (id, source, title, author, status, chapters, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''', (
                    book_info['id'], book_info.get('source', '未知来源'),
                    book_info['title'], book_info['author'],
                    book_info['status'], book_info['chapters'], metadata_str
                ))
            conn.commit()

        self._execute_with_retry(operation)

    def _add_book_to_category(self, book_id, category_name, cursor=None):
        """内部方法 - 将书籍添加到分类"""

        def operation(cursor, conn):
            cursor.execute("SELECT id FROM categories WHERE name=?", (category_name,))
            if category_row := cursor.fetchone():
                category_id = category_row[0]
            else:
                cursor.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
                category_id = cursor.lastrowid

            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO book_categories (book_id, category_id) VALUES (?, ?)",
                    (book_id, category_id)
                )
            except sqlite3.IntegrityError:
                pass  # 关系已存在

            # 修复：使用游标的连接对象提交
            cursor.connection.commit()  # 关键修改点

        if cursor:
            operation(cursor, None)
        else:
            with self.lock:
                self._execute_with_retry(operation)

    def save_reading_progress(self, book_id, current_chapter, chapter_position, bookmarked=False):
        """保存阅读进度 - 删除notes参数"""

        def operation(cursor, conn):
            now = datetime.now().isoformat()
            cursor.execute('''
                INSERT OR REPLACE INTO reading_progress 
                (book_id, current_chapter, chapter_position, last_read_time, bookmarked)
                VALUES (?, ?, ?, ?, ?)''', (
                book_id, current_chapter, chapter_position, now, bookmarked
            ))
            conn.commit()
            self._add_book_to_category(book_id, "最近阅读", cursor)

        with self.lock:
            self._execute_with_retry(operation)

    def get_book_downloads(self, book_id):
        """获取书籍的下载记录"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM downloads WHERE book_id = ?", (book_id,))
            return [dict(row) for row in cursor.fetchall()]

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

    def set_custom_db_path(self, new_folder):
        """设置自定义数据库文件夹路径并保存到配置文件"""
        os.makedirs(new_folder, exist_ok=True)
        self.db_path = os.path.join(new_folder, "novel_database.db")

        app_data_dir = self.get_app_data_dir()
        config_path = app_data_dir / "config.json"
        config = {}

        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass

        config["database_folder"] = new_folder
        app_data_dir.mkdir(parents=True, exist_ok=True)

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        self.init_database()

    def record_download(self, book_id, file_path, status="completed"):
        """记录下载信息 - 使用线程锁确保安全"""
        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            file_size = 0

        def operation(cursor, conn):
            cursor.execute('''
                INSERT INTO downloads (book_id, file_path, file_size, download_status)
                VALUES (?, ?, ?, ?)
            ''', (book_id, file_path, file_size, status))

            if status == "completed":
                self._add_book_to_category(book_id, "已下载", cursor)
            conn.commit()

        with self.lock:
            self._execute_with_retry(operation)

    def add_bookmark(self, book_id, chapter, position, note):
        """添加书签到数据库"""

        def operation(cursor, conn):
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL,
                    chapter INTEGER NOT NULL,
                    position REAL NOT NULL,
                    note TEXT,
                    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (book_id) REFERENCES books(id)
                )''')
            cursor.execute('''
                INSERT INTO bookmarks (book_id, chapter, position, note)
                VALUES (?, ?, ?, ?)
            ''', (book_id, chapter, position, note))
            conn.commit()
            return True

        try:
            return self._execute_with_retry(operation) is not None
        except Exception as e:
            print(f"添加书签失败: {e}")
            return False

    def get_reading_progress(self, book_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reading_progress WHERE book_id = ?", (book_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

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

    def toggle_bookmark(self, book_id):
        """切换收藏状态"""

        def operation(cursor, conn):
            cursor.execute("SELECT bookmarked FROM reading_progress WHERE book_id=?", (book_id,))
            if row := cursor.fetchone():
                new_value = 0 if row[0] else 1
                cursor.execute("UPDATE reading_progress SET bookmarked=? WHERE book_id=?", (new_value, book_id))
            else:
                new_value = 1
                cursor.execute("INSERT INTO reading_progress (book_id, bookmarked) VALUES (?, 1)", (book_id,))
            conn.commit()
            return new_value

        with self.lock:
            try:
                return self._execute_with_retry(operation)
            except Exception as e:
                print(f"切换收藏状态失败: {e}")
                return None

    def add_book_to_category(self, book_id, category_name):
        """将书籍添加到指定分类，如果分类不存在则创建"""

        def operation(cursor, conn):
            cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
            if category_row := cursor.fetchone():
                category_id = category_row[0]
            else:
                cursor.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
                category_id = cursor.lastrowid

            cursor.execute(
                "SELECT 1 FROM book_categories WHERE book_id = ? AND category_id = ?",
                (book_id, category_id)
            )
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO book_categories (book_id, category_id) VALUES (?, ?)",
                    (book_id, category_id)
                )
            conn.commit()
            return True

        return self._execute_with_retry(operation) or False

    def remove_book_from_category(self, book_id, category_name):
        """从分类中移除书籍"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
            if category := cursor.fetchone():
                cursor.execute(
                    "DELETE FROM book_categories WHERE book_id = ? AND category_id = ?",
                    (book_id, category[0])
                )
            conn.commit()

    def search_books_by_title(self, keyword):
        """按书名搜索书籍"""
        return self._query_books("SELECT * FROM books WHERE title LIKE ?", ('%' + keyword + '%',))

    def search_books_by_author(self, keyword):
        """按作者搜索书籍"""
        return self._query_books("SELECT * FROM books WHERE author LIKE ?", ('%' + keyword + '%',))

    def search_books(self, keyword):
        """全文搜索书籍（书名和作者）"""
        return self._query_books("""
            SELECT * FROM books 
            WHERE title LIKE ? OR author LIKE ?
        """, ('%' + keyword + '%', '%' + keyword + '%'))

    def get_recent_searches(self, limit=10):
        """获取最近搜索的书籍"""
        return self._query_books("""
            SELECT * FROM books 
            ORDER BY last_search DESC 
            LIMIT ?
        """, (limit,))

    def get_most_searched(self, limit=10):
        """获取搜索次数最多的书籍"""
        return self._query_books("""
            SELECT * FROM books 
            ORDER BY search_count DESC 
            LIMIT ?
        """, (limit,))

    def delete_book(self, book_id):
        """删除书籍及其相关记录"""

        def operation(cursor, conn):
            tables = [
                "downloads", "book_categories",
                "reading_progress", "reading_history"
            ]
            for table in tables:
                cursor.execute(f"DELETE FROM {table} WHERE book_id = ?", (book_id,))

            cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
            cursor.execute("DELETE FROM books_fts WHERE rowid IN (SELECT rowid FROM books WHERE id = ?)", (book_id,))
            conn.commit()

        self._execute_with_retry(operation)

    def export_library(self, export_path):
        """导出整个数据库到文件"""
        try:
            os.makedirs(export_path, exist_ok=True)
            db_export_path = os.path.join(export_path, "novel_library.db")

            with sqlite3.connect(self.db_path) as src, sqlite3.connect(db_export_path) as dest:
                src.backup(dest)

            # 元数据导出
            metadata_path = os.path.join(export_path, "metadata.json")
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "export_time": datetime.now().isoformat(),
                    "book_count": len(self.get_all_books()),
                    "download_count": len(self.get_all_downloads()),
                    "categories": self.get_categories()
                }, f, ensure_ascii=False, indent=2)

            # 导出下载文件
            downloads_dir = os.path.join(export_path, "downloads")
            os.makedirs(downloads_dir, exist_ok=True)
            for download in self.get_all_downloads():
                if os.path.exists(src_path := download['file_path']):
                    with open(src_path, 'rb') as src, open(os.path.join(downloads_dir, os.path.basename(src_path)),
                                                           'wb') as dest:
                        dest.write(src.read())

            # 导出阅读进度
            progress_path = os.path.join(export_path, "reading_progress.json")
            progress_data = {"progress": [], "history": []}

            for book in self.get_all_books():
                if progress := self.get_reading_progress(book['id']):
                    progress_data["progress"].append({
                        "book_id": book['id'],
                        "title": book['title'],
                        "current_chapter": progress['current_chapter'],
                        "chapter_position": progress['chapter_position'],
                        "last_read_time": progress['last_read_time']
                    })

                if history := self.get_reading_history(book['id']):
                    progress_data["history"].extend([{
                        "book_id": book['id'],
                        "title": book['title'],
                        "read_time": h['read_time'],
                        "duration": h['duration'],
                        "chapters_read": h['chapters_read']
                    } for h in history])

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

        def operation(cursor, conn):
            tables = [
                "downloads", "book_categories",
                "reading_progress", "reading_history"
            ]
            for table in tables:
                cursor.execute(f"""
                    DELETE FROM {table}
                    WHERE book_id NOT IN (SELECT id FROM books)
                """)
            conn.commit()

        self._execute_with_retry(operation)

    def calculate_file_hash(self, file_path):
        """计算文件的哈希值用于验证完整性"""
        if not os.path.exists(file_path):
            return None

        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def verify_downloads(self):
        """验证下载文件的完整性"""

        def operation(cursor, conn):
            cursor.execute("SELECT id, file_path FROM downloads")
            for download_id, file_path in cursor.fetchall():
                status = 'missing' if not os.path.exists(file_path) else 'verified'
                cursor.execute(
                    "UPDATE downloads SET download_status = ? WHERE id = ?",
                    (status, download_id)
                )
            conn.commit()

        self._execute_with_retry(operation)
