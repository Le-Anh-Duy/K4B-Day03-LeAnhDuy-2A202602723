# 📊 BÁO CÁO THU HOẠCH NGHIỆM THU BÀI LAB 3 (BƯỚC 3 — SUBMISSION ARTIFACT)

> **Họ và Tên Học viên:** Lê Anh Duy
> **Mã Sinh Viên / Mã Học viên:** 2A202602723  
> **Chủ đề Lựa chọn:** Trợ lý Quản lý Thư viện & Tài liệu: Tra cứu vị trí sách, tình trạng mượn/trả và gia hạn tài liệu.

---

## 1. BẢNG CHẤM ĐIỂM AGENTIC FIT SCORING MATRIX (ĐÁNH GIÁ CHỦ ĐỀ)

| Tiêu chí Đánh giá | Mức độ (1 - 5) | Giải trình chi tiết lý do chọn điểm |
| :--- | :---: | :--- |
| **1. Multi-step Reasoning** | 1 / 5 | Có nhưng không nhiều |
| **2. Tool Interaction** | 5 / 5 | Có cần kết nối với các tool truy vấn đến database, cần phải giao tiếp với database thư viện |
| **3. Dynamic Decision** | 4 / 5 | Có, nếu cần mượn 1 cuốn sách cần biết cuốn sách đó nằm ở đâu thì truy vấn vị trí và cần biết xem có còn sách để mượn không |
| **4. Long Horizon Goal** | 3 / 5 | Trong suốt quy trình cần tìm 1 cuốn sách thì cần giữ mục tiêu tìm sách qua nhiều step |
| **TỔNG ĐIỂM AGENTIC FIT** | **13 / 20** | Bài toán phù hợp với Agentic Fit |

---

## 2. TRÍCH XUẤT KẾT QUẢ WATERFALL TRACE LOG (SAU KHI CHẠY TEST SUITE TRÊN API THẬT)

> ⚠️ **YÊU CẦU NGHIỆM THU:** Mở tệp `.env` điền `GEMINI_API_KEY` (hoặc `OPENAI_API_KEY`) để kết nối LLM thật trước khi thực thi `python src/app.py --all`. Bài nộp chỉ dùng Mock Offline Provider sẽ không đạt điểm nghiệm thực tế.

Dán 1 đoạn trích xuất log tiêu biểu từ file `docs/trace_waterfall.json` sinh ra từ phản hồi LLM API thật:

```json
[
  {
    "step": 1,
    "query": "hãy gia hạn cho tôi tới ngày 20 tháng 10 nhé",
    "action_type": "TOOL_EXECUTION",
    "tool_name": "borrowed_documents",
    "arguments": {
      "student_id": "SV2026001"
    },
    "observation": {
      "status": "SUCCESS",
      "student_id": "SV2026001",
      "data": [
        {
          "document_id": "LIB002",
          "title": "Database System Concepts",
          "borrow_date": "2026-09-01",
          "due_date": "2026-09-15",
          "renewable": true
        }
      ],
      "message": "Sinh viên SV2026001 đang mượn 1 tài liệu: 'Database System Concepts' (Mã: LIB002, Hạn trả: 2026-09-15, Có thể gia hạn: Có)."
    },
    "latency_ms": 1255.03
  },
  {
    "step": 2,
    "query": "hãy gia hạn cho tôi tới ngày 20 tháng 10 nhé",
    "action_type": "TOOL_EXECUTION",
    "tool_name": "renew_document",
    "arguments": {
      "student_id": "SV2026001",
      "document_id": "LIB002"
    },
    "observation": {
      "status": "SUCCESS",
      "student_id": "SV2026001",
      "document_id": "LIB002",
      "new_due_date": "2026-09-29",
      "message": "Gia hạn tài liệu 'LIB002' ('Database System Concepts') thành công. Hạn trả mới là 2026-09-29."
    },
    "latency_ms": 1543.17
  },
  {
    "step": 3,
    "query": "hãy gia hạn cho tôi tới ngày 20 tháng 10 nhé",
    "action_type": "FINAL_ANSWER",
    "thought": "Gemini phản hồi trực tiếp bằng văn bản (không cần gọi công cụ).",
    "output": "Tài liệu \"Database System Concepts\" (mã LIB002) của bạn đã được gia hạn thành công. Hạn trả mới của tài liệu này là ngày 29 tháng 09 năm 2026.\n\nLưu ý rằng hệ thống thư viện chỉ cho phép gia hạn đến ngày 29/09/2026, vì vậy tôi không thể gia hạn đến ngày 20 tháng 10 như bạn mong muốn. Bạn vui lòng lưu ý thời hạn mới này để trả tài liệu đúng hạn nhé.",
    "latency_ms": 1869.51
  }
]
```

---

## 3. TỔNG KẾT KẾT QUẢ NGHIỆM THU & NỘP BÀI

- [x] Đã điền API Key thật trong `.env` và xác nhận Agent chạy mượt mà trên LLM API thật (Gemini/OpenAI).
- **Tổng số Test Cases đã chạy thành công:** 5 / 5 test cases.
- **Số lượt gọi Tool qua MCP Server chính xác:** 5 lượt.
- **Kết quả đẩy Repo nộp bài:** [x] Đã Commit và Push mã nguồn thành công lên GitHub cá nhân.

---

> ✅ **HOÀN TẤT NỘP BÀI:** Sao chép đường link GitHub Repository cá nhân của bạn và dán vào ô nộp bài trên hệ thống LMS VLearn để hoàn tất Bài Lab 3!
