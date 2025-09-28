import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from rag import RAGSystem
from llm import OlamaLLM
import config
import logging
import re

class BookStoreChatbot:
  def __init__(self):
      print("Đang khởi tạo BookStore Chatbot...")
      
      self.rag_system = RAGSystem()
      self.llm_handler = OlamaLLM()
      
      self.conversation_state = {}
      
      logging.basicConfig(level=logging.INFO)
      self.logger = logging.getLogger(__name__)
      
      print("BookStore Chatbot đã sẵn sàng!")
  
  def process_message(self, user_message, session_id = "default"):
        try:
            if session_id not in self.conversation_state:
                self.conversation_state[session_id] = {
                    "intent": None,
                    "pending_order": None,
                    "editing_fields": None,
                    "last_books": [],
                    "conversation_history": []
                }
            
            session = self.conversation_state[session_id]
            
            session["conversation_history"].append({
                "role": "user",
                "message": user_message
            })
            
            intent_result = self._enhanced_intent_classification(user_message, session)
            session["intent"] = intent_result["intent"]
            
            if session.get("editing_fields"):
                response = self._handle_order_edit(user_message, session_id)
            elif session.get("pending_order"):
                response = self._handle_order_confirmation(user_message, session_id)
            else:
                if intent_result["intent"] == "SEARCH":
                    response = self._handle_search_enhanced(user_message, intent_result, session_id)
                elif intent_result["intent"] == "ORDER":
                    response = self._handle_order_enhanced(user_message, intent_result, session_id)
                elif intent_result["intent"] == "ORDER_STATUS":
                    response = self._handle_order_status_enhanced(user_message, intent_result, session_id)
                else:
                    response = self._handle_general(user_message, session_id)
            
            session["conversation_history"].append({
                "role": "bot",
                "message": response
            })
            
            return response
                
        except Exception as e:
            self.logger.error(f"Lỗi khi xử lý tin nhắn: {e}")
            return "Xin lỗi, có lỗi xảy ra. Bạn có thể thử lại không?"
    
  def _enhanced_intent_classification(self, user_message, session):
        context = {
            "last_books": session.get("last_books", []),
            "pending_order": session.get("pending_order"),
            "conversation_history": session.get("conversation_history", [])[-3:]  # 3 tin nhắn gần nhất
        }
        
        return self.llm_handler.enhanced_intent_classification(user_message, context)
    
  def _handle_search_enhanced(self, user_message, intent_result, session_id):
        search_query = intent_result.get("extracted_info", {}).get("search_query", user_message)
        
        relevant_books = self.rag_system.retrieve_relevant_books(search_query)
        
        if not relevant_books:
            return "Xin lỗi, tôi không tìm thấy sách nào phù hợp trong cửa hàng."
        
        self.conversation_state[session_id]["last_books"] = relevant_books
        
        return self.llm_handler.generate_search_response(search_query, relevant_books)
    
  def _handle_order_enhanced(self, user_message, intent_result, session_id):
        session = self.conversation_state[session_id]
        extracted_info = intent_result.get("extracted_info", {})
        
        book_info = self._find_book_for_order_enhanced(user_message, extracted_info, session)
        
        if not book_info:
            return "Bạn muốn đặt sách nào? Vui lòng cho tôi biết tên sách cụ thể hoặc tìm kiếm sách trước."
        
        if book_info['stock'] <= 0:
            return f"Xin lỗi, sách '{book_info['title']}' hiện đã hết hàng."
        
        order_info = self._create_order_info_enhanced(book_info, extracted_info, user_message)
        
        return self._process_order_workflow(order_info, session_id)
    
  def _find_book_for_order_enhanced(self, user_message, extracted_info, session):
        if extracted_info.get("book_title"):
            book_info = self.rag_system.find_book_for_order(extracted_info["book_title"])
            if book_info:
                return book_info
        
        referenced_book = self._extract_book_reference(user_message, session.get("last_books", []))
        if referenced_book:
            return referenced_book
        
        enhanced_info = self.llm_handler.extract_order_info_enhanced(user_message, session.get("last_books", []))
        if enhanced_info.get("book_title"):
            book_info = self.rag_system.find_book_for_order(enhanced_info["book_title"])
            if book_info:
                return book_info
        
        return None
    
  def _create_order_info_enhanced(self, book_info, extracted_info, user_message):
        if not all([extracted_info.get('quantity'), extracted_info.get('customer_name')]):
            enhanced_info = self.llm_handler.extract_order_info_enhanced(user_message)
            extracted_info.update({k: v for k, v in enhanced_info.items() if v})
        
        return {
            'book_title': book_info['title'],
            'book_id': book_info['book_id'],
            'book_info': book_info,
            'quantity': extracted_info.get('quantity', 1),
            'customer_name': extracted_info.get('customer_name'),
            'phone': extracted_info.get('phone'),
            'address': extracted_info.get('address')
        }
    
  def _handle_order_status_enhanced(self, user_message, intent_result, session_id):
        phone = intent_result.get("extracted_info", {}).get("phone")
        
        if not phone:
            phone = self._extract_phone_fallback(user_message)
        
        if not phone:
            return "Vui lòng cung cấp số điện thoại để tra cứu đơn hàng."
        
        orders = self.rag_system.db.get_orders_by_phone(phone)
        
        if not orders:
            return f"Không tìm thấy đơn hàng nào cho số điện thoại **{phone}**."
        
        response = f"**ĐƠN HÀNG CỦA BẠN (SĐT: {phone}):**\n\n"
        
        for i, order in enumerate(orders, 1):
            total_price = order['quantity'] * order['price_per_book']
            
            response += f"""
**Đơn hàng #{i}**
- Mã đơn: #{order['order_id']}
- Sách: {order['book_title']}
- Số lượng: {order['quantity']} quyển
- Đơn giá: {order['price_per_book']:,} VND
- Tổng tiền: {total_price:,} VND
- Tên: {order['customer_name']}
- SĐT: {order['phone']}
- Địa chỉ: {order['address']}
- Trạng thái: {order['status']}
- Ngày đặt: {order['created_at']}
────────────────────
"""
        return response
    
  def _extract_phone_fallback(self, user_message):
        clean_message = re.sub(r'\s+', '', user_message.strip())
        
        if re.fullmatch(r'(\+?[0-9]{10,12})', clean_message):
            return clean_message
        
        phone_match = re.search(r'(\+?[0-9]{10,12})', user_message)
        if phone_match:
            return phone_match.group(1)
        
        return None
  
  def _classify_intent_simple(self, user_message, session):
    message_lower = user_message.lower()
    
    clean_message = re.sub(r'\s+', '', user_message.strip())
    
    if re.fullmatch(r'(\+?[0-9]{10,12})', clean_message):
        return "ORDER_STATUS"
    
    phone_patterns = [
        r'sdt[:\s]*(\+?[0-9]{10,12})',
        r'số[:\s]*(\+?[0-9]{10,12})', 
        r'phone[:\s]*(\+?[0-9]{10,12})',
        r'điện\s*thoại[:\s]*(\+?[0-9]{10,12})'
    ]
    
    for pattern in phone_patterns:
        if re.search(pattern, message_lower, re.IGNORECASE):
            return "ORDER_STATUS"
    
    order_status_keywords = [
        'trạng thái đơn hàng', 'tra cứu đơn hàng', 'đơn hàng của tôi', 
        'kiểm tra đơn hàng', 'order status', 'track order'
    ]
    
    if any(keyword in message_lower for keyword in order_status_keywords):
        return "ORDER_STATUS"
    
    # Kiểm tra đặt hàng
    order_keywords = ['đặt', 'mua', 'order', 'buy', 'muốn mua', 'cần mua', 'đặt hàng']
    if any(keyword in message_lower for keyword in order_keywords):
        return "ORDER"
    
    # Kiểm tra tìm kiếm
    search_keywords = ['tìm', 'search', 'có sách', 'sách nào', 'recommend', 'gợi ý', 'tư vấn']
    if any(keyword in message_lower for keyword in search_keywords):
        return "SEARCH"
    
    return "GENERAL"
  
  def _handle_search(self, user_message, session_id):
      try:
          relevant_books = self.rag_system.retrieve_relevant_books(
              user_message, 
              top_k=config.SEARCH_TOP_K
          )
          
          if not relevant_books:
              return "Xin lỗi, tôi không tìm thấy sách nào phù hợp trong cửa hàng. Bạn có thể thử từ khóa khác không?"
          
          self.conversation_state[session_id]["last_books"] = relevant_books
          
          response = "**Tôi tìm thấy những cuốn sách sau:**\n\n"
          
          for i, book in enumerate(relevant_books, 1):
              stock_status = "Còn hàng" if book['stock'] > 0 else "❌ Hết hàng"
              response += f"""**{i}. {book['title']}**
- Tác giả: {book['author']}
- Thể loại: {book['category']}
- Giá: {book['price']:,} VND
- Tình trạng: {stock_status} ({book['stock']} quyển)
- Mô tả: {book.get('description', 'Không có mô tả')[:100]}...

"""
          
          response += "\nBạn có thể nói đặt hàng nếu muốn!"
          
          return response
          
      except Exception as e:
          self.logger.error(f"Lỗi trong _handle_search: {e}")
          return "Xin lỗi, có lỗi khi tìm kiếm sách. Bạn có thể thử lại không?"
  
  def _handle_order(self, user_message: str, session_id: str) -> str:
      try:
          session = self.conversation_state[session_id]
          
          referenced_book = self._extract_book_reference(user_message, session.get("last_books", []))
          
          if referenced_book:
              return self._process_book_order(referenced_book, user_message, session_id)
          else:
              book_title = self._extract_book_title_from_order(user_message)
              
              if book_title:
                  book_info = self.rag_system.find_book_for_order(book_title)
                  
                  if book_info:
                      return self._process_book_order(book_info, user_message, session_id)
                  else:
                      return f"Xin lỗi, tôi không tìm thấy sách '{book_title}' trong cửa hàng. Bạn có thể tìm kiếm sách trước không?"
              else:
                  return "Bạn muốn đặt sách gì? Vui lòng cho tôi biết tên sách hoặc tìm kiếm sách trước nhé!"
              
      except Exception as e:
          self.logger.error(f"Lỗi trong _handle_order: {e}")
          return "Có lỗi khi xử lý đơn hàng. Vui lòng thử lại."
  
  def _handle_order_status(self, user_message, session_id):
    try:
        clean_message = re.sub(r'\s+', '', user_message.strip())
        
        if re.fullmatch(r'(\+?[0-9]{10,12})', clean_message):
            phone = clean_message
        else:
            phone_match = re.search(r'(\+?[0-9]{10,12})', user_message)
            if phone_match:
                phone = phone_match.group(1)
            else:
                customer_info = self._extract_customer_info(user_message)
                phone = customer_info.get('phone')
        
        if not phone:
            return """
**TRA CỨU ĐƠN HÀNG**

Vui lòng cung cấp số điện thoại đã dùng khi đặt hàng.

**Cách cung cấp:**
"0123456789"
"""
        
        print(f"Đang tra cứu đơn hàng với SĐT: {phone}")  # Debug
        
        orders = self.rag_system.db.get_orders_by_phone(phone)
        
        print(f"Tìm thấy {len(orders)} đơn hàng")  # Debug
        
        if not orders:
            return f"Không tìm thấy đơn hàng nào cho số điện thoại **{phone}**."
        
        response = f"**ĐƠN HÀNG CỦA BẠN (SĐT: {phone}):**\n\n"
        
        for i, order in enumerate(orders, 1):
            total_price = order['quantity'] * order['price_per_book']
            
            response += f"""
        **Đơn hàng #{i}**
        - Mã đơn: #{order['order_id']}
        - Sách: {order['book_title']}
        - Số lượng: {order['quantity']} quyển
        - Đơn giá: {order['price_per_book']:,} VND
        - Tổng tiền: {total_price:,} VND
        - Tên: {order['customer_name']}
        - SĐT: {order['phone']}
        - Địa chỉ: {order['address']}
        - Trạng thái: {order['status']}
        - Ngày đặt: {order['created_at']}
        ────────────────────
        """
        return response
        
    except Exception as e:
        self.logger.error(f"Lỗi tra cứu đơn hàng: {e}")
        return f"Có lỗi khi tra cứu đơn hàng: {e}"
    
  def _extract_book_reference(self, user_message, last_books):
    if not last_books:
        return None
        
    message_lower = user_message.lower()
    
    number_patterns = [
        (r'cuốn\s*(?:số\s*)?(\d+)', lambda m: int(m.group(1)) - 1),
        (r'sách\s*(?:số\s*)?(\d+)', lambda m: int(m.group(1)) - 1),
        (r'(?:thứ|số)\s*(\d+)', lambda m: int(m.group(1)) - 1),
        (r'quyển\s*(\d+)', lambda m: int(m.group(1)) - 1),
    ]
    
    for pattern, extractor in number_patterns:
        match = re.search(pattern, message_lower)
        if match:
            try:
                index = extractor(match)
                if 0 <= index < len(last_books):
                    return last_books[index]
            except:
                continue
    
    # Từ tham chiếu
    ref_words = {
        'này': 0, 'đó': 0, 'kia': 0, 'trên': 0, 
        'đầu tiên': 0, 'đầu': 0, 'first': 0,
        'thứ hai': 1, 'thứ 2': 1, 'second': 1,
        'thứ ba': 2, 'thứ 3': 2, 'third': 2,
        'cuối': -1, 'last': -1, 'cuối cùng': -1
    }
    
    for word, index in ref_words.items():
        if word in message_lower:
            if index == -1:  # cuối cùng
                return last_books[-1] if last_books else None
            elif index < len(last_books):
                return last_books[index]
    
    return None
  
  def _process_order_workflow(self, order_info, session_id):
        session = self.conversation_state[session_id]
        
        missing_info = self._check_missing_order_info(order_info)
        
        if missing_info:
            session["pending_order"] = order_info
            missing_text = self._get_missing_field_names(missing_info)
            
            return f"""
**THÔNG TIN ĐẶT HÀNG HIỆN TẠI:**
- Sách: {order_info['book_info']['title']}
- Số lượng: {order_info.get('quantity', 'CHƯA CÓ')}
- Tên: {order_info.get('customer_name', 'CHƯA CÓ')}
- SĐT: {order_info.get('phone', 'CHƯA CÓ')}
- Địa chỉ: {order_info.get('address', 'CHƯA CÓ')}

**THIẾU THÔNG TIN:** {', '.join(missing_text)}

**Vui lòng cung cấp đầy đủ thông tin theo mẫu:**
"Tên: [họ tên], Số lượng: [số quyển], SĐT: [số điện thoại], Địa chỉ: [địa chỉ]"
"""
        else:
            session["pending_order"] = order_info
            return self._generate_order_confirmation_message(order_info)
        
  def _extract_book_title_from_order(self, user_message):
      message_lower = user_message.lower()
      
      # Pattern để tìm tên sách
      patterns = [
          r'đặt (?:sách |cuốn )?["\']?([^"\']+)["\']?',
          r'mua (?:sách |cuốn )?["\']?([^"\']+)["\']?',
          r'order (?:sách |cuốn )?["\']?([^"\']+)["\']?',
          r'tôi muốn (?:mua |đặt )?(?:sách |cuốn )?["\']?([^"\']+)["\']?',
      ]
      
      for pattern in patterns:
          match = re.search(pattern, message_lower)
          if match:
              title = match.group(1).strip()
              # Loại bỏ các từ không cần thiết
              stop_words = ['với', 'số lượng', 'quyển', 'cuốn', 'tên là', 'có tên']
              for word in stop_words:
                  if word in title:
                      title = title.split(word)[0].strip()
              return title
      
      return None
  
  def _process_book_order(self, book_info, user_message, session_id):
    if book_info['stock'] <= 0:
        return f"Xin lỗi, sách '{book_info['title']}' hiện đã hết hàng."
    
    quantity = self._extract_quantity(user_message)
    
    customer_info = self._extract_customer_info(user_message)
    
    order_info = {
        'book_title': book_info['title'],
        'book_id': book_info['book_id'],
        'quantity': quantity,
        'book_info': book_info,
        **customer_info
    }
    
    missing_info = self._check_missing_order_info(order_info)
    
    if missing_info:
        self.conversation_state[session_id]["pending_order"] = order_info
        
        missing_text = self._get_missing_field_names(missing_info)
        response = f"""
**THÔNG TIN ĐẶT HÀNG HIỆN TẠI:**
- Sách: {book_info['title']}
- Số lượng: {quantity if quantity > 0 else 'CHƯA CÓ'}
- Tên: {customer_info.get('customer_name', 'CHƯA CÓ')}
- SĐT: {customer_info.get('phone', 'CHƯA CÓ')}
- Địa chỉ: {customer_info.get('address', 'CHƯA CÓ')}

**THIẾU THÔNG TIN:** {', '.join(missing_text)}
        
**Vui lòng cung cấp đầy đủ thông tin theo mẫu:**
"Tên: [họ tên], Số lượng: [số quyển], SĐT: [số điện thoại], Địa chỉ: [địa chỉ]"

**Ví dụ:** "Tên: Nguyễn Văn A, Số lượng: 2, SĐT: 0123456789, Địa chỉ: Hà Nội"
"""
        return response
    else:
        self.conversation_state[session_id]["pending_order"] = order_info
        return self._generate_order_confirmation_message(order_info)
  
  def _check_missing_order_info(self, order_info):
    missing = []
    
    if not order_info.get('quantity') or order_info['quantity'] <= 0:
        missing.append('quantity')
    if not order_info.get('customer_name'):
        missing.append('customer_name')
    if not order_info.get('phone'):
        missing.append('phone')
    if not order_info.get('address'):
        missing.append('address')
    
    return missing

  def _get_missing_field_names(self, missing_fields):
    field_names = {
        'quantity': 'số lượng',
        'customer_name': 'tên khách hàng',
        'phone': 'số điện thoại',
        'address': 'địa chỉ'
    }
    return [field_names[field] for field in missing_fields]

  def _generate_order_confirmation_message(self, order_info):
    total_price = order_info['book_info']['price'] * order_info['quantity']
    
    return f"""
**THÔNG TIN ĐƠN HÀNG:**

- Sách: {order_info['book_info']['title']}
- Tên: {order_info['customer_name']}
- SĐT: {order_info['phone']}
- Địa chỉ: {order_info['address']}
- Số lượng: {order_info['quantity']} quyển
- Tổng tiền: {total_price:,} VND

**Thông tin trên có chính xác không?**
- Trả lời 'có' hoặc 'đúng' để xác nhận đặt hàng
- Trả lời 'sửa [tên/sđt/địa chỉ/số lượng]' để chỉnh sửa
- Trả lời 'hủy' để hủy đơn hàng
"""

  def _extract_quantity(self, user_message):
    message_lower = user_message.lower()
    
    # Từ khóa số lượng bằng chữ
    quantity_words = {
        'một': 1, 'hai': 2, 'ba': 3, 'bốn': 4, 'năm': 5,
        'sáu': 6, 'bảy': 7, 'tám': 8, 'chín': 9, 'mười': 10
    }
    
    for word, num in quantity_words.items():
        if word in message_lower:
            return num
    
    quantity_patterns = [
        r'số\s*lượng\s*:\s*(\d+)',  
        r'số\s*lượng\s*:\s*(\d+)',  
        r'số\s*lượng\s*:\s*(\d+)',  
        r'số\s*lượng\s+(\d+)',      
        r'quantity\s*:\s*(\d+)',     
        r'qty\s*:\s*(\d+)',          
        r'(\d+)\s*quyển',
        r'(\d+)\s*cuốn',
        r'mua\s*(\d+)',
        r'đặt\s*(\d+)'
    ]
    
    for pattern in quantity_patterns:
        try:
            matches = re.finditer(pattern, message_lower)
            for match in matches:
                quantity = int(match.group(1))
                if 1 <= quantity <= 100:
                    return quantity
        except:
            continue
    
    if any(word in message_lower for word in ['số lượng', 'quantity', 'qty', 'quyển', 'cuốn']):
        numbers = re.findall(r'\b\d+\b', message_lower)
        for num_str in numbers:
            try:
                quantity = int(num_str)
                if 1 <= quantity <= 100:
                    return quantity
            except:
                continue
    
    return 0  

  def _extract_customer_info(self, user_message):
    customer_info = {
        'customer_name': None,
        'phone': None,
        'address': None
    }
    
    clean_message = re.sub(r'\s+', '', user_message.strip())
    if re.fullmatch(r'(\+?[0-9]{10,12})', clean_message):
        customer_info['phone'] = clean_message
        return customer_info
    
    phone_patterns = [
        r'(?:sdt|phone|điện\s*thoại|số|tel)[\s:\-]*(\+?[0-9\s\-]{10,12})',
        r'(?:sdt|phone|số)[\s:\-]*là[\s:\-]*(\+?[0-9\s\-]{10,12})',
        r'(?:sdt|phone|số)[\s:\-]*của\s*tôi[\s:\-]*(\+?[0-9\s\-]{10,12})',
        r'(?:sdt|phone|số)[\s:\-]*của\s*tôi[\s:\-]*là[\s:\-]*(\+?[0-9\s\-]{10,12})',
        r'(\+?0?[0-9]{9,11})' 
    ]
    
    for pattern in phone_patterns:
        matches = re.finditer(pattern, user_message, re.IGNORECASE)
        for match in matches:
            phone = re.sub(r'[\s\-]+', '', match.group(1))
            if 10 <= len(phone) <= 12:
                customer_info['phone'] = phone
                break
        if customer_info['phone']:
            break
    
    name_patterns = [
        r'tên[\s:\-]*([a-zA-ZÀ-ỹ\s]{2,})',
        r'tôi\s*tên\s*là[\s:\-]*([a-zA-ZÀ-ỹ\s]{2,})',
        r'tên[\s:\-]*tôi[\s:\-]*là[\s:\-]*([a-zA-ZÀ-ỹ\s]{2,})',
        r'name[\s:\-]*([a-zA-ZÀ-ỹ\s]{2,})'
    ]
    
    for pattern in name_patterns:
        matches = re.finditer(pattern, user_message, re.IGNORECASE)
        for match in matches:
            name = match.group(1).strip()
            if len(name.split()) >= 1:
                customer_info['customer_name'] = name
                break
        if customer_info['customer_name']:
            break
    
    address_patterns = [
        r'địa\s*chỉ[\s:\-]*(.+?)(?=\s*(?:sdt|phone|tên|name|$))',
        r'address[\s:\-]*(.+?)(?=\s*(?:sdt|phone|tên|name|$))',
        r'địa\s*chỉ[\s:\-]*giao\s*hàng[\s:\-]*(.+?)(?=\s*(?:sdt|phone|tên|name|$))'
    ]
    
    for pattern in address_patterns:
        matches = re.finditer(pattern, user_message, re.IGNORECASE)
        for match in matches:
            address = match.group(1).strip()
            if len(address) > 5:
                customer_info['address'] = address
                break
        if customer_info['address']:
            break
    
    form_patterns = [
        r'tên[\s:\-]*([^,]+?)(?:\s*[,]|$)',
        r'sđt[\s:\-]*([^,]+?)(?:\s*[,]|$)',
        r'địa\s*chỉ[\s:\-]*([^,]+?)(?:\s*[,]|$)'
    ]
    
    if not customer_info['customer_name']:
        for pattern in form_patterns:
            match = re.search(pattern, user_message, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if 'tên' in pattern and len(value) > 1:
                    customer_info['customer_name'] = value
                    break
    
    return customer_info
  
  def _handle_order_confirmation(self, user_message: str, session_id: str) -> str:
    session = self.conversation_state[session_id]
    pending_order = session["pending_order"]
    
    message_lower = user_message.lower()
    
    if any(word in message_lower for word in ['sửa', 'thay đổi', 'sai', 'edit', 'change']):
        return self._handle_order_edit(message_lower, session_id)
    
    if any(word in message_lower for word in ['có', 'đúng', 'chính xác', 'yes', 'ok', 'xác nhận']):
        missing_info = self._check_missing_order_info(pending_order)
        if missing_info:
            missing_text = self._get_missing_field_names(missing_info)
            return f"Vẫn còn thiếu thông tin: {', '.join(missing_text)}. Vui lòng cung cấp đầy đủ."
        
        try:
            order_id = self.rag_system.db.create_order(
                customer_name=pending_order['customer_name'],
                phone=pending_order['phone'],
                address=pending_order['address'],
                book_id=pending_order['book_id'],
                quantity=pending_order['quantity']
            )
            
            session["pending_order"] = None
            
            return f"""
**ĐẶT HÀNG THÀNH CÔNG!**

- Mã đơn hàng: #{order_id}
- Sách: {pending_order['book_info']['title']}
- Số lượng: {pending_order['quantity']} quyển
- Tổng tiền: {pending_order['book_info']['price'] * pending_order['quantity']:,} VND

Chúng tôi sẽ liên hệ với bạn trong vòng 24h để xác nhận và giao hàng.

Cảm ơn bạn đã mua sắm tại BookStore!
"""
        except Exception as e:
            session["pending_order"] = None
            return f"Có lỗi xảy ra khi tạo đơn hàng: {e}. Vui lòng thử lại."
    
    # Xử lý hủy đơn hàng
    elif any(word in message_lower for word in ['hủy', 'cancel', 'không', 'no', 'thôi']):
        session["pending_order"] = None
        return "Đã hủy đơn hàng. Bạn có cần hỗ trợ gì khác không?"
    
    else:
        updated_info = self._extract_customer_info(user_message)
        quantity = self._extract_quantity(user_message)
        
        for key, value in updated_info.items():
            if value:
                pending_order[key] = value
        if quantity > 0:
            pending_order['quantity'] = quantity
        
        missing_info = self._check_missing_order_info(pending_order)
        
        if missing_info:
            missing_text = self._get_missing_field_names(missing_info)
            return f"""
**ĐÃ CẬP NHẬT THÔNG TIN**

Thông tin hiện tại:
- Sách: {pending_order['book_info']['title']}
- Số lượng: {pending_order.get('quantity', 0)} quyển
- Tên: {pending_order.get('customer_name', 'CHƯA CÓ')}
- SĐT: {pending_order.get('phone', 'CHƯA CÓ')}
- Địa chỉ: {pending_order.get('address', 'CHƯA CÓ')}

**VẪN THIẾU:** {', '.join(missing_text)}
"""
        else:
            return self._generate_order_confirmation_message(pending_order)

  def _handle_order_edit(self, message_lower, session_id):
    session = self.conversation_state[session_id]
    # pending_order = session["pending_order"]
    
    fields_to_edit = []
    if any(word in message_lower for word in ['tên', 'name']):
        fields_to_edit.append('customer_name')
    if any(word in message_lower for word in ['số điện thoại', 'sdt', 'sđt', 'điện thoại', 'phone']):
        fields_to_edit.append('phone')
    if any(word in message_lower for word in ['địa chỉ', 'address', 'địa chỉ giao hàng']):
        fields_to_edit.append('address')
    if any(word in message_lower for word in ['số lượng', 'quantity', 'số quyển']):
        fields_to_edit.append('quantity')
    
    if not fields_to_edit:
        return "Bạn muốn sửa thông tin gì? (tên, số điện thoại, địa chỉ, số lượng). Vui lòng nói rõ."
    
    session["editing_fields"] = fields_to_edit
    
    field_names = {
        'customer_name': 'tên',
        'phone': 'số điện thoại',
        'address': 'địa chỉ',
        'quantity': 'số lượng'
    }
    
    fields_text = [field_names[field] for field in fields_to_edit]
    
    return f"Vui lòng cung cấp {' và '.join(fields_text)} mới. Ví dụ: 'Tên: Nguyễn Văn A, SĐT: 0123456789'"
  
  def _handle_general(self, user_message, session_id):
      try:
          return self.llm_handler.generate_general_response(user_message)
      except:
          return """
Xin chào! Tôi là trợ lý BookStore. Tôi có thể giúp bạn:

**Tìm kiếm sách:** "Tìm sách về lập trình"
**Đặt hàng:** "Đặt sách Nhà Giả Kim"
**Gợi ý:** "Gợi ý sách hay"

Bạn cần tôi hỗ trợ gì?
"""
  
  def get_system_stats(self):
      return self.rag_system.get_statistics()
  
#   def get_conversation_history(self, session_id):
#       session = self.conversation_state.get(session_id, {})
#       return session.get("conversation_history", [])
  
#   def reset_conversation(self, session_id):
#       if session_id in self.conversation_state:
#           del self.conversation_state[session_id]

# Test function
if __name__ == "__main__":
  chatbot = BookStoreChatbot()
  
  print("\nBookStore Chatbot")
  print("Gõ 'quit' để thoát, 'stats' để xem thống kê\n")
  
  while True:
      user_input = input("Bạn: ")
      if user_input.lower() == 'quit':
          break
      elif user_input.lower() == 'stats':
          stats = chatbot.get_system_stats()
          print(f"Thống kê: {stats}")
          continue
      
      response = chatbot.process_message(user_input)
      print(f"Bot: {response}\n")