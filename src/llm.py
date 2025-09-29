import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ollama
import json
import re
from config import OLLAMA_MODEL
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OlamaLLM:
    def __init__(self):
        model_name = OLLAMA_MODEL
        self.model_name = model_name
        self.client = ollama.Client()

        try:
            self.client.chat(model=model_name, messages=[{"role": "user", "content": "test"}])
            logger.info(f"Model {model_name} đã sẵn sàng")
        except Exception as e:
            logger.info(f"Lỗi kết nối với {model_name}")
            logger.info(f"Vui lòng đảm bảo rằng bạn đã cài đặt Ollama và pull Llama3.1:8b")
    
    def enhanced_intent_classification(self, user_message, context = None):
        rule_based_result = self._rule_based_intent_detection(user_message)
        
        if rule_based_result["confidence"] < 0.7:
            llm_result = self._llm_intent_detection(user_message, context)
            if llm_result["confidence"] > rule_based_result["confidence"]:
                return llm_result
        
        return rule_based_result
    
    def _rule_based_intent_detection(self, user_message):
        message_lower = user_message.lower()
        confidence = 1.0
        
        clean_message = re.sub(r'\s+', '', user_message.strip())
        if re.fullmatch(r'(\+?[0-9]{10,12})', clean_message):
            return {
                "intent": "ORDER_STATUS", 
                "confidence": 1.0,
                "extracted_info": {"phone": clean_message}
            }
        
        phone_patterns = [
            r'sdt[:\s]*(\+?[0-9]{10,12})', r'số[:\s]*(\+?[0-9]{10,12})',
            r'phone[:\s]*(\+?[0-9]{10,12})', r'điện\s*thoại[:\s]*(\+?[0-9]{10,12})'
        ]
        
        for pattern in phone_patterns:
            match = re.search(pattern, message_lower, re.IGNORECASE)
            if match:
                return {
                    "intent": "ORDER_STATUS",
                    "confidence": 0.9,
                    "extracted_info": {"phone": match.group(1)}
                }
        
        order_status_keywords = ['trạng thái đơn hàng', 'tra cứu đơn hàng', 'đơn hàng của tôi']
        order_keywords = ['đặt', 'mua', 'order', 'buy', 'muốn mua', 'đặt hàng', 'đặt sách']
        search_keywords = ['tìm', 'search', 'có sách', 'sách nào', 'recommend','sách gì']
        
        if any(keyword in message_lower for keyword in order_status_keywords):
            return {"intent": "ORDER_STATUS", "confidence": 0.9, "extracted_info": {}}
        elif any(keyword in message_lower for keyword in order_keywords):
            return {"intent": "ORDER", "confidence": 0.8, "extracted_info": {}}
        elif any(keyword in message_lower for keyword in search_keywords):
            return {"intent": "SEARCH", "confidence": 0.8, "extracted_info": {}}
        
        return {"intent": "GENERAL", "confidence": 0.5, "extracted_info": {}}
    
    def _llm_intent_detection(self, user_message, context = None):
        prompt = f"""
Phân tích ý định người dùng và trích xuất thông tin từ câu: "{user_message}"

Context: {context}

Phân loại thành một trong:
- SEARCH: tìm kiếm, hỏi thông tin sách
- ORDER: đặt mua sách 
- ORDER_STATUS: tra cứu đơn hàng
- GENERAL: câu hỏi chung

Trả về JSON: {{"intent": "...", "confidence": 0.0-1.0, "extracted_info": {{...}}}}

Thông tin có thể trích xuất:
- book_title: tên sách
- quantity: số lượng
- customer_name: tên KH
- phone: số điện thoại
- address: địa chỉ
- search_query: từ khóa tìm kiếm
"""

        try:
            response = self.client.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1}
            )
            
            import json
            result = json.loads(response['message']['content'])
            return result
            
        except Exception as e:
            return {"intent": "GENERAL", "confidence": 0.3, "extracted_info": {}}
    
    def extract_order_info(self, user_message, available_books = None):
        books_text = ""
        if available_books:
            books_text = "\n".join([f"- {book['title']} (ID: {book['book_id']})" for book in available_books])
        
        prompt = f"""
        Trích xuất thông tin đặt hàng từ: "{user_message}"
        
        Sách có sẵn: {books_text}
        
        Trả về JSON:
        {{
            "book_title": "tên sách",
            "quantity": số_lượng,
            "customer_name": "tên KH", 
            "phone": "số điện thoại",
            "address": "địa chỉ",
            "confidence": 0.0-1.0
        }}
        """

        try:
            response = self.client.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1}
            )
            
            import json
            content = response['message']['content']
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            
            if json_match:
                result = json.loads(json_match.group())
                # Đảm bảo có quantity mặc định
                if not result.get('quantity'):
                    result['quantity'] = 1
                return result
            else:
                return {"quantity": 1, "confidence": 0.5}
                
        except Exception as e:
            return {"quantity": 1, "confidence": 0.3}
    
    def generate_search_response(self, user_query, books_info):
        if not books_info:
            return "Xin lỗi tôi không thể tìm thấy bất kỳ cuốn sách nào phù hợp với yêu cầu của bạn"
        
        books_text = ""
        for i, book in enumerate(books_info[:3], 1):
            books_text += f"""
{i}. **{book['title']}**
- Tác giả: {book['author']}
- Thể loại: {book['category']}  
- Giá: {book['price']:,} VND
- Tồn kho: {book['stock']} quyển
"""
        
        prompt = f"""
Bạn là nhân viên tư vấn sách. Khách hàng hỏi: "{user_query}"

Sách tìm thấy:
{books_text}

Hãy tạo phản hồi thân thiện, giới thiệu các sách này và hỏi xem họ có muốn đặt mua không.
Giữ nguyên thông tin giá và số lượng.
"""

        try:
            response = self.client.chat(
                model=self.model_name,
                messages=[{"role":"user", "content": prompt}],
                options={"temperature": 0.7}
            )
            return response['message']['content']
        except Exception as e:
            logger.error(f"Lỗi khi sinh phản hồi tìm kiếm: {e}")
            return f"Tìm thấy {len(books_info)} sách phù hợp:\n{books_text}"
    
    def generate_general_response(self, user_message):
      prompt = f"""
      Bạn là nhân viên tư vấn của cửa hàng sách BookStore. Khách hàng đã hỏi: "{user_message}"
      
      Hãy trả lời một cách thân thiện và chuyên nghiệp. Nếu câu hỏi không liên quan đến sách, hãy lịch sự chuyển hướng về việc tư vấn sách.
      """
      
      try:
          response = self.client.chat(
              model=self.model_name,
              messages=[{"role": "user", "content": prompt}],
              options={"temperature": 0.7}
          )
          return response['message']['content']
      except Exception as e:
          print(f"Lỗi khi tạo phản hồi chung: {e}")
          return "Xin chào! Tôi có thể giúp bạn tìm kiếm sách hoặc đặt hàng. Bạn cần hỗ trợ gì?"