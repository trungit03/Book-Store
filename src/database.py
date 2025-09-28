import os
import sqlite3
import json

class BookStoreDB:
    def __init__(self, db_path="data/books.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
                       book_id INTEGER PRIMARY KEY AUTOINCREMENT,
                       title nvarchar(50) NOT NULL,
                       author nvarchar(50) NOT NULL,
                       price double NOT NULL,
                       stock INTEGER NOT NULL,
                       category nvarchar(50) NOT NULL,
                       description nvarchar(100)
                       )
''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
                       order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                       customer_name nvarchar(50) NOT NULL,
                       phone varchar(11) NOT NULL,
                       address nvarchar(75) NOT NULL,
                       book_id INTEGER NOT NULL,
                       quantity INTEGER NOT NULL,
                       status nvarchar(10) DEFAULT 'pending',
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                       FOREIGN KEY (book_id) REFERENCES books (book_id)
                       )
''')
        conn.commit()
        conn.close()

        if self.count_books() == 0:
            self.insert_data()
    
    def insert_data(self):
        books_data = [
            {
                "title": "Đắc Nhân Tâm",
                "author": "Dale Carnegie",
                "price": 85000,
                "stock": 50,
                "category": "Phát triển bản thân",
                "description": "Cuốn sách kinh điển về nghệ thuật giao tiếp và ứng xử"
            },

            {
              "title": "Sapiens: Lược sử loài người",
              "author": "Yuval Noah Harari",
              "price": 120000,
              "stock": 30,
              "category": "Lịch sử",
              "description": "Câu chuyện về sự tiến hóa của loài người từ thời tiền sử đến hiện đại"
          },

          {
              "title": "Atomic Habits",
              "author": "James Clear",
              "price": 95000,
              "stock": 25,
              "category": "Phát triển bản thân",
              "description": "Hướng dẫn xây dựng thói quen tốt và loại bỏ thói quen xấu"
          },

          {
              "title": "Tôi Tài Giỏi, Bạn Cũng Thế",
              "author": "Adam Khoo",
              "price": 75000,
              "stock": 40,
              "category": "Giáo dục",
              "description": "Phương pháp học tập hiệu quả cho học sinh và sinh viên"
          },

          {
              "title": "Nhà Giả Kim",
              "author": "Paulo Coelho",
              "price": 65000,
              "stock": 60,
              "category": "Tiểu thuyết",
              "description": "Câu chuyện về hành trình tìm kiếm kho báu và ý nghĩa cuộc sống"
          }
        ]

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for book in books_data:
            cursor.execute('''
                    INSERT INTO books (title, author, price, stock, category, description)
                    VALUES(?, ?, ? ,? ,?, ?)
        ''', (book["title"], book["author"], book["price"], 
               book["stock"], book["category"], book["description"]))
        
        conn.commit()
        conn.close()
    
    def search_books(self, query=None, category=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if query:
            cursor.execute('''
                SELECT * FROM books 
                WHERE title LIKE ? OR author LIKE ? OR description LIKE ?
        ''', (f'%{query}%', f'%{query}%', f'%{query}%'))
        elif category: 
            cursor.execute('SELECT * FROM books WHERE category = ?', (category, ))
        else:
            cursor.execute('SELECT * FROM books')
        
        books = cursor.fetchall()
        conn.close()

        return [self._row_to_dict(book) for book in books]
    
    def get_book_by_id(self, book_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM books WHERE book_id = ?', (book_id, ))
        book = cursor. fetchone()
        conn.close()
        
        return self._row_to_dict(book) if book else None
    
    def create_order(self, customer_name, phone, address, book_id, quantity):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
                INSERT INTO orders (customer_name, phone, address, book_id, quantity)
                VALUES (?, ?, ?, ?, ?)
        ''', (customer_name, phone, address, book_id, quantity))

        order_id = cursor.lastrowid

        cursor.execute('''
        UPDATE books 
        SET stock = stock - ? 
        WHERE book_id = ?
    ''', (quantity, book_id))
        
        conn.commit()
        conn.close()

        return order_id
    
    def count_books(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM books')
        count = cursor.fetchone()[0]
        conn.close()

        return count
    
    def _row_to_dict(self, row):
        if not row:
            return None
        
        return {
            'book_id': row[0],
            'title': row[1],
            'author': row[2],
            'price': row[3],
            'stock': row[4],
            'category': row[5],
            'description': row[6] if len(row) > 6 else ''
        }
    
    def get_orders_by_phone(self, phone):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT o.*, b.title, b.price 
            FROM orders o 
            JOIN books b ON o.book_id = b.book_id 
            WHERE o.phone = ?
            ORDER BY o.created_at DESC
        ''', (phone,))
        
        orders = cursor.fetchall()
        conn.close()
        
        result = []
        for order in orders:
            result.append({
                'order_id': order[0],
                'customer_name': order[1],
                'phone': order[2],
                'address': order[3],
                'book_id': order[4],
                'quantity': order[5],
                'status': order[6],
                'created_at': order[7],
                'book_title': order[8],
                'price_per_book': order[9] 
            })
        
        return result