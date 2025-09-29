import os
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
import json
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import EMBEDDING_MODEL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmbeddingManager:
    def __init__(self):
        model_name = EMBEDDING_MODEL.split('/')[-1] if '/' in EMBEDDING_MODEL else EMBEDDING_MODEL
        self.model_name = model_name
        logger.info(f"Loading embedding model: {self.model_name}")

        try:
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Embedding model '{self.model_name}' đã tải.")
        except Exception as e:
            logger.error(f"Thất bại khi tải embedding model '{self.model_name}': {e}")
            self.model = None  

        self.chroma_client = chromadb.PersistentClient(path="data/chromadb")
        self.collection = self.chroma_client.get_or_create_collection(
            name="books_collection",
            metadata={"hnsw:space":"cosine"}
        )

        logger.info(f"Embedding model: {self.model_name} đã sẵn sàng")

    def create_book_embeddings(self, books):
        logger.info("Đang tạo embeddings cho sách...")

        try:
            self.chroma_client.delete_collection("books_collection")
            logger.info("Collection cũ đã xóa.")
        except Exception:
            logger.info("Không tồn tại collection để xóa.")

        self.collection = self.chroma_client.get_or_create_collection(
            name="books_collection",
            metadata={"hnsw:space": "cosine"}
        )

        documents = []
        metadatas = []
        ids = []

        for book in books:
            text = f"""
            Tên sách: {book['title']}
            Tác giả: {book['author']}
            Thể loại: {book['category']}
            Mô tả: {book.get('description', '')}
            Giá: {book['price']} VND
            Tồn kho: {book['stock']} quyển
            """.strip()

            documents.append(text)
            metadatas.append({
                "book_id": book['book_id'],
                "title": book['title'],
                "author": book['author'],
                "price": book['price'],
                "stock": book['stock'],
                "category": book['category']
            })
            ids.append(f"book_{book['book_id']}")

        # Thêm dữ liệu mới
        if documents:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"Đang tạo embeddings cho {len(books)} sách.")
        else:
            logger.warning("Không sách nào cung cấp, collection rỗng.")

    
    def search_similar_books(self, query, top_k = 5):
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k
        )

        similar_books = []
        if results['metadatas'] and results['metadatas'][0]:
            for metadata, distance in zip(results['metadatas'][0], results['distances'][0]):
                book_info = metadata.copy()
                book_info['similarity_score'] = 1 - distance

                similar_books.append(book_info)

        
        return similar_books
    