"""
🛠️ TOOL DEFINITIONS & EXECUTION BACKEND

Mã nguồn chứa danh sách Tool Schemas (JSON Sche
và Execution Layer phục vụ cho Library Assistant (Trợ lý Thư viện).
Hỗ trợ tìm kiếm tài liệu đa năng: Theo mã sách, tên sách (keyword/fuzzy search),
tác giả, và tra cứu/gia hạn tài liệu mượn.
"""

import json
import re
import sys
import unicodedata
import difflib
from typing import Dict, Any, Optional, List

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


# ==============================================================================
# 1. KHAI BÁO TOOL SCHEMAS CHUẨN NATIVE JSON SCHEMA
# ==============================================================================

TOOLS_SCHEMA = [

    # --------------------------------------------------------------------------
    # Tool 1: Tra cứu vị trí và thông tin tài liệu (Keyword & Fuzzy Search)
    # --------------------------------------------------------------------------
    {
        "name": "library_search",
        "description": (
            "Tra cứu thông tin, vị trí và trạng thái của sách, tài liệu trong thư viện. "
            "Hỗ trợ tìm kiếm linh hoạt theo: "
            "1) Mã tài liệu (document_id, ví dụ: 'LIB001'), "
            "2) Tên sách hoặc tiêu đề (title, ví dụ: 'Introduction to Computer Science', 'Database System Concepts'), "
            "3) Tên tác giả (author, ví dụ: 'Stuart Russell', 'John Smith'), "
            "4) Từ khóa tìm kiếm chung hoặc tên gần đúng khi không nhớ chính xác tên sách (query - hỗ trợ keyword search và fuzzy search)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Từ khóa tìm kiếm chung hoặc tiêu đề sách gần đúng khi người dùng không nhớ rõ tên "
                        "(hỗ trợ tìm kiếm mờ - fuzzy search, tìm theo chủ đề hoặc từ khóa tiếng Việt/Anh)."
                    )
                },
                "document_id": {
                    "type": "string",
                    "description": "Mã tài liệu cụ thể nếu đã biết chính xác, ví dụ: 'LIB001'."
                },
                "title": {
                    "type": "string",
                    "description": "Tiêu đề hoặc một phần tên sách cần tra cứu (ví dụ: 'Introduction to Computer Science')."
                },
                "author": {
                    "type": "string",
                    "description": "Tên tác giả cần tìm sách (ví dụ: 'Stuart Russell', 'Abraham Silberschatz')."
                }
            }
        }
    },

    # --------------------------------------------------------------------------
    # Tool 2: Tra cứu tình trạng mượn/trả của sinh viên
    # --------------------------------------------------------------------------
    {
        "name": "borrowed_documents",
        "description": "Tra cứu danh sách tài liệu mà sinh viên đang mượn, ngày mượn và hạn trả.",
        "parameters": {
            "type": "object",
            "properties": {
                "student_id": {
                    "type": "string",
                    "description": "Mã sinh viên cần tra cứu, ví dụ: 'SV2026001'"
                }
            },
            "required": ["student_id"]
        }
    },

    # --------------------------------------------------------------------------
    # Tool 3: Gia hạn tài liệu
    # --------------------------------------------------------------------------
    {
        "name": "renew_document",
        "description": "Gia hạn thời hạn trả một tài liệu mà sinh viên đang mượn.",
        "parameters": {
            "type": "object",
            "properties": {
                "student_id": {
                    "type": "string",
                    "description": "Mã sinh viên yêu cầu gia hạn"
                },
                "document_id": {
                    "type": "string",
                    "description": "Mã tài liệu cần gia hạn, ví dụ: 'LIB001'"
                }
            },
            "required": ["student_id", "document_id"]
        }
    }
]


# ==============================================================================
# 2. MOCK DATABASE (CƠ SỞ DỮ LIỆU THƯ VIỆN)
# ==============================================================================

MOCK_DATABASE = {
    "documents": {
        "LIB001": {
            "title": "Introduction to Computer Science",
            "author": "John Smith",
            "category": "Computer Science",
            "location": "Thư viện tầng 2 - Kệ A03",
            "status": "AVAILABLE",
            "keywords": [
                "nhập môn khoa học máy tính",
                "tin học đại cương",
                "lập trình cơ bản",
                "computer science",
                "cs",
                "john smith"
            ]
        },
        "LIB002": {
            "title": "Database System Concepts",
            "author": "Abraham Silberschatz",
            "category": "Database",
            "location": "Thư viện tầng 2 - Kệ B05",
            "status": "BORROWED",
            "keywords": [
                "hệ quản trị cơ sở dữ liệu",
                "nguyên lý cơ sở dữ liệu",
                "sql",
                "dbms",
                "database",
                "silberschatz"
            ]
        },
        "LIB003": {
            "title": "Artificial Intelligence: A Modern Approach",
            "author": "Stuart Russell",
            "category": "Artificial Intelligence",
            "location": "Thư viện tầng 3 - Kệ C02",
            "status": "AVAILABLE",
            "keywords": [
                "trí tuệ nhân tạo",
                "tiếp cận hiện đại",
                "học máy",
                "ai",
                "machine learning",
                "stuart russell",
                "modern approach"
            ]
        },
        "LIB004": {
            "title": "Clean Code: A Handbook of Agile Software Craftsmanship",
            "author": "Robert C. Martin",
            "category": "Software Engineering",
            "location": "Thư viện tầng 2 - Kệ A05",
            "status": "AVAILABLE",
            "keywords": [
                "mã sạch",
                "lập trình sạch",
                "kỹ thuật phần mềm",
                "uncle bob",
                "robert martin",
                "clean code"
            ]
        },
        "LIB005": {
            "title": "Deep Learning",
            "author": "Ian Goodfellow, Yoshua Bengio, Aaron Courville",
            "category": "Artificial Intelligence",
            "location": "Thư viện tầng 3 - Kệ C05",
            "status": "AVAILABLE",
            "keywords": [
                "học sâu",
                "mạng nơ-ron",
                "neural networks",
                "deep learning",
                "goodfellow"
            ]
        }
    },

    "borrow_records": {
        "SV2026001": [
            {
                "document_id": "LIB002",
                "title": "Database System Concepts",
                "borrow_date": "2026-09-01",
                "due_date": "2026-09-15",
                "renewable": True
            }
        ],

        "SV2026002": [
            {
                "document_id": "LIB003",
                "title": "Artificial Intelligence: A Modern Approach",
                "borrow_date": "2026-09-05",
                "due_date": "2026-09-19",
                "renewable": True
            }
        ]
    }
}


# ==============================================================================
# 3. THUẬT TOÁN HỖ TRỢ TÌM KIẾM MỜ (FUZZY & KEYWORD SEARCH)
# ==============================================================================

def _normalize_text(text: str) -> str:
    """Chuẩn hóa chuỗi: chuyển chữ thường, loại bỏ dấu tiếng Việt và ký tự đặc biệt."""
    if not text:
        return ""
    text = text.lower().strip()
    nfkd = unicodedata.normalize('NFKD', text)
    text_no_accents = ''.join([c for c in nfkd if not unicodedata.combining(c)])
    text_no_accents = text_no_accents.replace('đ', 'd').replace('Đ', 'd')
    text_clean = re.sub(r'[^\w\s]', ' ', text_no_accents)
    return re.sub(r'\s+', ' ', text_clean).strip()


def _calculate_field_similarity(query: str, target: str) -> float:
    """
    Tính điểm tương đồng giữa truy vấn (query) và trường dữ liệu (target).
    Kết hợp:
    1. Khớp chính xác hoàn toàn (1.0)
    2. Khớp chuỗi con (substring match)
    3. Khớp tập hợp từ khóa (token overlap)
    4. Fuzzy ratio toàn chuỗi (difflib SequenceMatcher)
    5. Fuzzy ratio qua cửa sổ trượt (sliding window matching)
    """
    q = _normalize_text(query)
    t = _normalize_text(target)
    if not q or not t:
        return 0.0

    if q == t:
        return 1.0

    scores = [0.0]

    # 1. Khớp chuỗi con
    if q in t:
        scores.append(0.85 + 0.15 * (len(q) / len(t)))
    if t in q:
        scores.append(0.80 + 0.15 * (len(t) / len(q)))

    # 2. Khớp tập hợp từ khóa (Token Overlap)
    q_words = [w for w in q.split() if len(w) > 1]
    t_words = set(t.split())
    if q_words and t_words:
        matched = [w for w in q_words if w in t_words]
        if len(matched) == len(q_words):
            scores.append(0.82 + 0.15 * (len(matched) / max(len(t_words), 1)))
        elif len(matched) > 0:
            scores.append(0.45 + 0.35 * (len(matched) / len(q_words)))

    # 3. Fuzzy ratio toàn chuỗi
    scores.append(difflib.SequenceMatcher(None, q, t).ratio())

    # 4. Fuzzy ratio trượt theo cửa sổ từ
    t_words_list = t.split()
    q_words_list = q.split()
    k = len(q_words_list)
    if 1 <= k < len(t_words_list):
        for i in range(len(t_words_list) - k + 1):
            window = " ".join(t_words_list[i : i + k])
            scores.append(difflib.SequenceMatcher(None, q, window).ratio())

    return max(scores)


# ==============================================================================
# 4. HÀM THỰC THI TOOL
# ==============================================================================

def execute_library_search(
    query: Optional[str] = None,
    document_id: Optional[str] = None,
    title: Optional[str] = None,
    author: Optional[str] = None,
    **kwargs
) -> str:
    """
    Tra cứu thông tin và vị trí tài liệu trong thư viện.
    Hỗ trợ tìm kiếm theo:
    - Mã tài liệu (document_id)
    - Tên sách (title)
    - Tác giả (author)
    - Từ khóa chung hoặc tên gần đúng (query) với cơ chế Fuzzy Search / Keyword Matching
    """
    # 1. Tra cứu theo document_id cụ thể nếu có
    if document_id:
        doc_id_clean = document_id.strip().upper()
        doc = MOCK_DATABASE["documents"].get(doc_id_clean)
        if doc:
            return json.dumps({
                "status": "SUCCESS",
                "search_mode": "EXACT_ID",
                "document_id": doc_id_clean,
                "data": {
                    "document_id": doc_id_clean,
                    **doc
                },
                "message": (
                    f"Tìm thấy tài liệu '{doc['title']}' (Mã: {doc_id_clean}) của tác giả {doc['author']}. "
                    f"Vị trí: {doc['location']}. Trạng thái: {doc['status']}."
                )
            }, ensure_ascii=False)
        elif not query and not title and not author and not kwargs:
            # Giữ đúng hành vi khi truyền document_id không tồn tại (TC05)
            return json.dumps({
                "status": "NOT_FOUND",
                "message": f"Không tìm thấy tài liệu có mã '{document_id}'."
            }, ensure_ascii=False)

    # 2. Thu thập các tham số tìm kiếm (hỗ trợ cả alias trong kwargs)
    search_title = title or kwargs.get("book_name") or kwargs.get("book_title")
    search_author = author or kwargs.get("writer") or kwargs.get("author_name")
    search_query = query or kwargs.get("keyword") or kwargs.get("search_term") or kwargs.get("search_query")

    # Kiểm tra nếu query thực chất là một mã document_id (ví dụ người dùng nhập 'LIB001' vào ô tìm kiếm)
    if search_query:
        query_as_id = search_query.strip().upper()
        if query_as_id in MOCK_DATABASE["documents"]:
            doc = MOCK_DATABASE["documents"][query_as_id]
            return json.dumps({
                "status": "SUCCESS",
                "search_mode": "EXACT_ID",
                "document_id": query_as_id,
                "data": {
                    "document_id": query_as_id,
                    **doc
                },
                "message": (
                    f"Tìm thấy tài liệu '{doc['title']}' (Mã: {query_as_id}) của tác giả {doc['author']}. "
                    f"Vị trí: {doc['location']}. Trạng thái: {doc['status']}."
                )
            }, ensure_ascii=False)

    # Nếu không cung cấp bất kỳ tiêu chí nào
    if not search_title and not search_author and not search_query:
        return json.dumps({
            "status": "ERROR",
            "message": "Vui lòng cung cấp mã tài liệu, tên sách, tên tác giả hoặc từ khóa tìm kiếm."
        }, ensure_ascii=False)

    # 3. Tính điểm độ tương đồng cho từng tài liệu
    candidates = []
    for did, doc in MOCK_DATABASE["documents"].items():
        doc_title = doc["title"]
        doc_author = doc["author"]
        doc_cat = doc.get("category", "")
        keywords = doc.get("keywords", [])

        scores = []

        if search_title:
            s_t = max(
                _calculate_field_similarity(search_title, doc_title),
                max([_calculate_field_similarity(search_title, kw) for kw in keywords] or [0.0])
            )
            scores.append(s_t)

        if search_author:
            s_a = _calculate_field_similarity(search_author, doc_author)
            scores.append(s_a)

        if search_query:
            s_q = max(
                _calculate_field_similarity(search_query, doc_title),
                _calculate_field_similarity(search_query, doc_author),
                _calculate_field_similarity(search_query, doc_cat),
                max([_calculate_field_similarity(search_query, kw) for kw in keywords] or [0.0])
            )
            scores.append(s_q)

        final_score = max(scores) if scores else 0.0

        if final_score >= 0.55:
            candidates.append((did, doc, final_score))

    # Sắp xếp kết quả theo điểm số giảm dần
    candidates.sort(key=lambda x: x[2], reverse=True)

    # 4. Trả kết quả
    if not candidates:
        criteria_parts = []
        if search_title: criteria_parts.append(f"tên sách: '{search_title}'")
        if search_author: criteria_parts.append(f"tác giả: '{search_author}'")
        if search_query: criteria_parts.append(f"từ khóa: '{search_query}'")
        query_desc = ", ".join(criteria_parts) if criteria_parts else "tiêu chí đã cung cấp"
        return json.dumps({
            "status": "NOT_FOUND",
            "message": f"Không tìm thấy tài liệu phù hợp với {query_desc} trong thư viện."
        }, ensure_ascii=False)

    # Nếu chỉ có 1 kết quả hoặc kết quả hàng đầu vượt trội rõ rệt
    if len(candidates) == 1 or (candidates[0][2] >= 0.85 and candidates[0][2] - candidates[1][2] >= 0.20):
        best_id, best_doc, best_score = candidates[0]
        mode = "EXACT_MATCH" if best_score >= 0.95 else "FUZZY_MATCH"
        return json.dumps({
            "status": "SUCCESS",
            "search_mode": mode,
            "similarity_score": round(best_score, 2),
            "document_id": best_id,
            "data": {
                "document_id": best_id,
                **best_doc
            },
            "message": (
                f"Tìm thấy tài liệu '{best_doc['title']}' (Mã: {best_id}) của tác giả {best_doc['author']}. "
                f"Vị trí: {best_doc['location']}. Trạng thái: {best_doc['status']}."
            )
        }, ensure_ascii=False)

    # Trường hợp tìm thấy nhiều tài liệu phù hợp
    return json.dumps({
        "status": "SUCCESS",
        "search_mode": "MULTI_MATCH",
        "total_found": len(candidates),
        "data": [
            {"document_id": did, **dinfo} for did, dinfo, score in candidates
        ],
        "message": (
            f"Tìm thấy {len(candidates)} tài liệu phù hợp: " +
            "; ".join([
                f"'{dinfo['title']}' (Mã: {did}, Vị trí: {dinfo['location']}, Trạng thái: {dinfo['status']})"
                for did, dinfo, score in candidates
            ])
        )
    }, ensure_ascii=False)


def execute_borrowed_documents(student_id: str) -> str:
    """Tra cứu các tài liệu sinh viên đang mượn."""
    student_id = student_id.strip().upper()
    records = MOCK_DATABASE["borrow_records"].get(student_id)

    if records is not None:
        if len(records) > 0:
            doc_summary = "; ".join([
                f"'{r['title']}' (Mã: {r['document_id']}, Hạn trả: {r['due_date']}, Có thể gia hạn: {'Có' if r.get('renewable') else 'Không'})"
                for r in records
            ])
            msg = f"Sinh viên {student_id} đang mượn {len(records)} tài liệu: {doc_summary}."
        else:
            msg = f"Sinh viên {student_id} hiện không mượn tài liệu nào."

        return json.dumps({
            "status": "SUCCESS",
            "student_id": student_id,
            "data": records,
            "message": msg
        }, ensure_ascii=False)

    return json.dumps({
        "status": "NOT_FOUND",
        "message": f"Không tìm thấy thông tin mượn/trả của sinh viên '{student_id}'."
    }, ensure_ascii=False)


def execute_renew_document(
    student_id: str,
    document_id: str
) -> str:
    """Gia hạn tài liệu sinh viên đang mượn."""
    student_id = student_id.strip().upper()
    document_id = document_id.strip().upper()

    records = MOCK_DATABASE["borrow_records"].get(student_id)

    if records is None:
        return json.dumps({
            "status": "NOT_FOUND",
            "message": f"Không tìm thấy thông tin mượn của sinh viên '{student_id}'."
        }, ensure_ascii=False)

    for record in records:
        if record["document_id"] == document_id:

            if not record.get("renewable", False):
                return json.dumps({
                    "status": "RENEWAL_DENIED",
                    "message": f"Tài liệu '{document_id}' không đủ điều kiện gia hạn (đã hết lượt gia hạn)."
                }, ensure_ascii=False)

            # Mock việc gia hạn thêm 14 ngày
            new_due_date = "2026-09-29"
            record["due_date"] = new_due_date
            record["renewable"] = False

            return json.dumps({
                "status": "SUCCESS",
                "student_id": student_id,
                "document_id": document_id,
                "new_due_date": new_due_date,
                "message": (
                    f"Gia hạn tài liệu '{document_id}' ('{record.get('title', '')}') thành công. "
                    f"Hạn trả mới là {new_due_date}."
                )
            }, ensure_ascii=False)

    return json.dumps({
        "status": "NOT_FOUND",
        "message": f"Sinh viên '{student_id}' hiện không mượn tài liệu '{document_id}'."
    }, ensure_ascii=False)


# ==============================================================================
# 5. TOOL ROUTER
# ==============================================================================

TOOL_ROUTER = {
    "library_search": execute_library_search,
    "borrowed_documents": execute_borrowed_documents,
    "renew_document": execute_renew_document
}


def dispatch_tool_call(
    tool_name: str,
    arguments: Dict[str, Any]
) -> str:
    """Hàm trung chuyển thực thi tool."""
    if tool_name in TOOL_ROUTER:
        try:
            return TOOL_ROUTER[tool_name](**arguments)
        except Exception as e:
            return json.dumps({
                "status": "EXECUTION_ERROR",
                "error": str(e)
            }, ensure_ascii=False)

    return json.dumps({
        "status": "UNKNOWN_TOOL",
        "error": f"Tool '{tool_name}' không tồn tại!"
    }, ensure_ascii=False)


# ==============================================================================
# 6. KIỂM THỬ ĐỘC LẬP (SELF-TEST)
# ==============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🛠️ KIỂM THỬ ĐỘC LẬP TOOLS CHO TRỢ LÝ THƯ VIỆN (LIBRARY ASSISTANT)")
    print("=" * 60)

    test_cases = [
        ("1. Tìm theo mã chính xác (document_id)", {"document_id": "LIB001"}),
        ("2. Tìm theo tên chính xác (title - TC02)", {"title": "Introduction to Computer Science"}),
        ("3. Tìm mờ gõ sai tên (fuzzy search)", {"query": "Introducton to Computer Sience"}),
        ("4. Tìm theo từ khóa trong tên (keyword)", {"query": "database"}),
        ("5. Tìm theo tên tác giả (author)", {"author": "Stuart Russell"}),
        ("6. Tìm theo tác giả gõ sai (fuzzy author)", {"query": "Stuart Rusel"}),
        ("7. Tìm theo tác giả viết tắt (partial author)", {"author": "Russell"}),
        ("8. Tìm theo từ khóa tiếng Việt", {"query": "trí tuệ nhân tạo"}),
        ("9. Tra cứu mã không tồn tại (TC05)", {"document_id": "LIB9999999"}),
        ("10. Tra cứu tài liệu sinh viên đang mượn (TC03)", {"student_id": "SV2026001"}),
        ("11. Gia hạn tài liệu (TC04)", {"student_id": "SV2026001", "document_id": "LIB002"}),
    ]

    for title, args in test_cases:
        print(f"\n👉 {title}:")
        print(f"   Tham số: {args}")
        if "student_id" in args and "document_id" in args:
            output = dispatch_tool_call("renew_document", args)
        elif "student_id" in args:
            output = dispatch_tool_call("borrowed_documents", args)
        else:
            output = dispatch_tool_call("library_search", args)
        parsed = json.loads(output)
        status_icon = "✅" if parsed.get("status") == "SUCCESS" else "⚠️"
        print(f"   {status_icon} Phản hồi [{parsed.get('status')}]: {parsed.get('message', parsed)}")

    print("\n" + "=" * 60)
    print("🎉 Hoàn tất kiểm thử các công cụ!")