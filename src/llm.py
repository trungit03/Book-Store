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
    
    def classify_intent(self, user_message):
        prompt =f"""
        Phân loại ý định của khách hàng. Chỉ trả lời một trong các từ khóa sau:

        - "SEARCH": Nếu khách hàng muốn tìm kiếm, hỏi thông tin sách (ví dụ: "tìm sách", "có sách nào về", "giới thiệu sách")

        - "ORDER": Nếu khách hàng muốn đặt mua, mua sách (ví dụ: "tôi muốn mua", "đặt sách", "mua quyển", "đặt hàng")

        - "ORDER_STATUS": Nếu khách hàng muốn tra cứu đơn hàng (ví dụ: tra cứu đơn hàng, đơn hàng của tôi)
        
        - "GENERAL": Nếu là câu hỏi chung khác

        Câu hỏi của khách hàng: "{user_message}"

        Ý định:
        """

        try:
            response = self.client.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature":0.1}
            )

            intent = response['message']['content'].strip().upper()
            user_message_lower = user_message.lower()
            order_keywords = ['mua', 'đặt', 'order', 'mua sách', 'đặt sách', 'mua quyển', 'đặt mua']
            
            order_status_keywords = ['tra cứu đơn hàng', 'đơn hàng của tôi']

            if any(keyword in user_message_lower for keyword in order_keywords):
                return "ORDER"
            
            if any(keyword in user_message_lower for keyword in order_status_keywords):
                return "ORDER_STATUS"
            
            if intent in ["SEARCH", "ORDER", "ORDER_STATUS", "GENERAL"]:
                return intent
            else:
                return "GENERAL"
        except Exception as e:
            logger.warning(f"Lỗi khi phân loại: {e}")
            return "GENERAL"
    
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
        order_keywords = ['đặt', 'mua', 'order', 'buy', 'muốn mua']
        search_keywords = ['tìm', 'search', 'có sách', 'sách nào', 'recommend']
        
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
    
    def extract_order_info_enhanced(self, user_message, available_books = None):
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
        # Giữ nguyên hàm cũ nhưng cải tiến
        if not books_info:
            return "Xin lỗi tôi không thể tìm thấy bất kỳ cuốn sách nào phù hợp với yêu cầu của bạn"
        
        # Dùng LLM để tạo response tự nhiên hơn
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
            return f"Tìm thấy {len(books_info)} sách phù hợp:\n{books_text}"
    
    def extract_order_info(self, user_message, available_books):
        books_list = "\n".join([f" - {book['title']} (ID: {book['book_id']})" for book in available_books])

        prompt = f"""
        Trích xuất thông tin đặt hàng từ tin nhắn của khách hàng.

    Danh sách sách có sẵn:
    {books_list}

    Tin nhắn khách hàng: "{user_message}"

    Trả về thông tin dưới dạng JSON với các trường:
    {{
        "book_title": "tên sách khách muốn mua",
        "quantity": số_lượng (số nguyên, phải hỏi khách xác nhận số lượng. Nếu đã có số lượng rồi thì không cần hỏi lại),
        "customer_name": "tên khách hàng",
        "phone": "số điện thoại",
        "address": "địa chỉ"
    }}

    Nếu thông tin bị thiếu, để giá trị là null.
    """

        try:
            response = self.client.chat(
                model =self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature":0.1}
            )

            content = response['message']['content']
            json_match = re.search(r'\{.*\}', content, re.DOTALL)

            if json_match:
                order_info = json.loads(json_match.group())
                if not order_info.get('quantity'):
                    order_info['quantity'] = 1
                return order_info
            else:
                return {"quantity": 1} 
        except Exception as e:
            logger.error(f"Error while extracting order information: {e}")
            return {"quantity": 1}
        
    def generate_order_response(self, order_info, book_info):
        if not order_info:
            return """
        Để đặt hàng, tôi cần thông tin sau:
          1. Tên sách bạn muốn mua
          2. Số lượng
          3. Tên của bạn
          4. Số điện thoại
          5. Địa chỉ nhận hàng
          
          Bạn có thể cung cấp thông tin theo mẫu: "Tôi muốn mua [tên sách] [số lượng] quyển. Tên tôi là [họ tên], số điện thoại [số ĐT], địa chỉ [địa chỉ]"
        
        """

        missing_info = []
        if not order_info.get('book_title'):
            missing_info.append("tên sách")
        if not order_info.get('quantity'):
          missing_info.append("số lượng")
        if not order_info.get('customer_name'):
            missing_info.append("tên khách hàng")
        if not order_info.get('phone'):
            missing_info.append("số điện thoại")
        if not order_info.get('address'):
            missing_info.append("địa chỉ")

        if missing_info:
            return f"Tôi cần thêm thông tin: {', '.join(missing_info)}. Bạn có thể cung cấp không?"
        
        total_price = book_info['price'] * order_info['quantity'] if book_info else 0

        return f"""
      **XÁC NHẬN ĐƠN HÀNG**
      
      - Sách: {order_info['book_title']}
      - Số lượng: {order_info['quantity']} quyển
      - Đơn giá: {book_info['price']:,} VND 
      - Tổng tiền: {total_price:,} VND
      
      Thông tin khách hàng:
      - Tên: {order_info['customer_name']}
      - SĐT: {order_info['phone']}
      - Địa chỉ: {order_info['address']}
      
      Bạn có xác nhận đặt hàng không? (Trả lời "có" để xác nhận)
      """
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