import numpy as np
from database import BookStoreDB
from src.embedding import EmbeddingManager
import config
import logging

class RAGSystem:
  def __init__(self):
      self.db = BookStoreDB()
      self.embedding_handler = EmbeddingManager()
      
      logging.basicConfig(level=logging.INFO)
      self.logger = logging.getLogger(__name__)
      
      self._initialize_embeddings()
      
  def _initialize_embeddings(self):
      try:
          books = self.db.search_books()
          if books:
              self.embedding_handler.create_book_embeddings(books)
              self.logger.info(f"Đã khởi tạo embeddings cho {len(books)} cuốn sách")
          else:
              self.logger.warning("Không có sách nào trong database")
      except Exception as e:
          self.logger.error(f"Lỗi khởi tạo embeddings: {e}")
  
  def retrieve_relevant_books(self, query, top_k = None):
      if top_k is None:
          top_k = config.SEARCH_TOP_K
          
      try:
          all_books = self.db.search_books()
          if not all_books:
              return []
          
          text_search_results = self.db.search_books(query=query)
          
          similar_books = []
          try:
              similar_books = self.embedding_handler.search_similar_books(query, top_k * 2)
              valid_similar_books = []
              for book in similar_books:
                  db_book = self.db.get_book_by_id(book['book_id'])
                  if db_book:
                      db_book['similarity_score'] = book.get('similarity_score', 0)
                      valid_similar_books.append(db_book)
              similar_books = valid_similar_books
          except Exception as e:
              self.logger.warning(f"Vector search failed: {e}, fallback to text search")
              similar_books = []
          
          merged_results = self._merge_search_results(similar_books, text_search_results)
          
          ranked_results = self._rank_results(merged_results, query)
          
          return ranked_results[:top_k]
          
      except Exception as e:
          self.logger.error(f"Lỗi trong retrieve_relevant_books: {e}")
          return self.db.search_books(query=query)[:top_k] if top_k else self.db.search_books(query=query)
  
  def _merge_search_results(self, vector_results, text_results):
      merged = {}
      
      for book in vector_results:
          book_id = book['book_id']
          merged[book_id] = book.copy()
          merged[book_id]['search_type'] = 'vector'
      
      for book in text_results:
          book_id = book['book_id']
          if book_id not in merged:
              book_copy = book.copy()
              book_copy['similarity_score'] = 0.5  
              book_copy['search_type'] = 'text'
              merged[book_id] = book_copy
          else:
              merged[book_id]['similarity_score'] = min(1.0, merged[book_id]['similarity_score'] + 0.2)
              merged[book_id]['search_type'] = 'hybrid'
      
      return list(merged.values())
  
  def _rank_results(self, results, query):
      for book in results:
          score = book.get('similarity_score', 0)
          
          if book.get('stock', 0) > 0:
              score += 0.1
          
          query_lower = query.lower()
          if query_lower in book.get('title', '').lower():
              score += 0.3
          if query_lower in book.get('author', '').lower():
              score += 0.2
          
          book['final_score'] = score
      
      return sorted(results, key=lambda x: x.get('final_score', 0), reverse=True)
  
  def get_context_for_llm(self, query, top_k = 3):
      try:
          relevant_books = self.retrieve_relevant_books(query, top_k)
          
          if not relevant_books:
              return "Không tìm thấy sách nào phù hợp trong cửa hàng."
          
          context_parts = []
          for i, book in enumerate(relevant_books, 1):
              context_part = f"""
Sách {i}:
- Tên: {book['title']}
- Tác giả: {book['author']}
- Thể loại: {book['category']}
- Giá: {book['price']:,} VND
- Tồn kho: {book['stock']} quyển
- Mô tả: {book.get('description', 'Không có mô tả')}
"""
              context_parts.append(context_part.strip())
          
          return "\n\n".join(context_parts)
          
      except Exception as e:
          self.logger.error(f"Lỗi tạo context cho LLM: {e}")
          return "Có lỗi xảy ra khi tìm kiếm thông tin sách."
  
  def find_book_for_order(self, book_title):
      try:
          books = self.db.search_books(query=book_title)
          
          if books:
              for book in books:
                  if book['title'].lower() == book_title.lower():
                      return book
              
              try:
                  similar_books = self.embedding_handler.search_similar_books(book_title, n_results=1)
                  if similar_books and similar_books[0].get('similarity_score', 0) > 0.8:
                      found_book = self.db.get_book_by_id(similar_books[0]['book_id'])
                      if found_book:
                          return found_book
              except:
                  pass
              
              return books[0]
          
          return None
          
      except Exception as e:
          self.logger.error(f"Lỗi tìm sách để đặt hàng: {e}")
          return None
  
  def find_book_by_reference(self, reference, last_books):
      if not last_books:
          return None
          
      reference_lower = reference.lower()
      
      # Mapping các từ tham chiếu
      if any(word in reference_lower for word in ['này', 'đó', 'kia', 'trên', 'đầu tiên', 'đầu', 'first']):
          return last_books[0]
      elif any(word in reference_lower for word in ['thứ hai', 'thứ 2', 'second', 'hai']):
          return last_books[1] if len(last_books) > 1 else None
      elif any(word in reference_lower for word in ['thứ ba', 'thứ 3', 'third', 'ba']):
          return last_books[2] if len(last_books) > 2 else None
      elif any(word in reference_lower for word in ['cuối', 'last', 'cuối cùng']):
          return last_books[-1]
      
      return None
  
  def get_books_by_category(self, category):
      try:
          return self.db.search_books(category=category)
      except Exception as e:
          self.logger.error(f"Lỗi lấy sách theo thể loại: {e}")
          return []
  
  def get_popular_books(self, limit = 5):
      try:
          all_books = self.db.search_books()
          popular = sorted(all_books, key=lambda x: x.get('stock', 0), reverse=True)
          return popular[:limit]
      except Exception as e:
          self.logger.error(f"Lỗi lấy sách phổ biến: {e}")
          return []
  
  def get_all_books(self):
      try:
          return self.db.search_books()
      except Exception as e:
          self.logger.error(f"Lỗi lấy tất cả sách: {e}")
          return []
  
  def refresh_embeddings(self):
      try:
          self._initialize_embeddings()
          self.logger.info("Đã refresh embeddings thành công")
      except Exception as e:
          self.logger.error(f"Lỗi refresh embeddings: {e}")
  
  def get_statistics(self):
      try:
          total_books = self.db.count_books()
          
          all_books = self.db.search_books()
          categories = {}
          for book in all_books:
              cat = book.get('category', 'Khác')
              categories[cat] = categories.get(cat, 0) + 1
          
          return {
              'total_books': total_books,
              'categories': categories,
              'embedding_model': config.EMBEDDING_MODEL,
              'vector_db_collection': config.CHROMA_COLLECTION_NAME
          }
      except Exception as e:
          self.logger.error(f"Lỗi lấy thống kê: {e}")
          return {}
