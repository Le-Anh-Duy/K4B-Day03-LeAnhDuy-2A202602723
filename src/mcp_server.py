"""
🔌 MODEL CONTEXT PROTOCOL (MCP) SERVER MODULE

Mô phỏng kiến trúc MCP Server (Client-Server Architecture)
cung cấp các công cụ quản lý thư viện và tài liệu.
"""

import json
import sys
from typing import Dict, Any, List

from tools import TOOLS_SCHEMA, dispatch_tool_call


# ==============================================================================
# CẤU HÌNH ENCODING
# ==============================================================================

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ==============================================================================
# MCP SERVER
# ==============================================================================

class MCPLibraryServer:
    """
    Giả lập MCP Server cho hệ thống Trợ lý Quản lý Thư viện & Tài liệu.
    """

    def __init__(
        self,
        server_name: str = "vinuni-library-mcp-server"
    ):
        self.server_name = server_name
        self.version = "2026.1.0"

    # --------------------------------------------------------------------------
    # LIST TOOLS
    # --------------------------------------------------------------------------

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        Trả về danh sách các Tools được MCP Server công bố.
        """
        return TOOLS_SCHEMA

    # --------------------------------------------------------------------------
    # CALL TOOL
    # --------------------------------------------------------------------------

    def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        [TASK 2.1]

        Thực thi request gọi Tool trên MCP Server.

        Quy trình:
        1. Gọi dispatch_tool_call() để thực thi Tool.
        2. Parse chuỗi JSON kết quả thành Python Dictionary.
        3. Đóng gói kết quả theo cấu trúc JSON-RPC 2.0.
        """

        # ----------------------------------------------------------------------
        # Bước 1: Gọi Tool Router
        # ----------------------------------------------------------------------

        raw_result = dispatch_tool_call(
            tool_name,
            arguments
        )

        # ----------------------------------------------------------------------
        # Bước 2: Chuyển chuỗi JSON thành Python Dictionary
        # ----------------------------------------------------------------------

        try:
            content = json.loads(raw_result)

        except json.JSONDecodeError:
            content = {
                "status": "EXECUTION_ERROR",
                "error": "Tool trả về dữ liệu JSON không hợp lệ."
            }

        # ----------------------------------------------------------------------
        # Bước 3: Đóng gói phản hồi JSON-RPC 2.0
        # ----------------------------------------------------------------------

        return {
            "jsonrpc": "2.0",
            "server": self.server_name,
            "tool": tool_name,
            "result": content
        }


# ==============================================================================
# KIỂM THỬ ĐỘC LẬP MCP SERVER
# ==============================================================================

if __name__ == "__main__":

    print("==========================================================")
    print("🔌 KIỂM THỬ ĐỘC LẬP MCP SERVER")
    print("   Trợ lý Quản lý Thư viện & Tài liệu")
    print("==========================================================")

    # --------------------------------------------------------------------------
    # Khởi tạo Server
    # --------------------------------------------------------------------------

    server = MCPLibraryServer()

    tools = server.list_tools()

    print(
        f"✅ Khởi tạo thành công MCP Server: "
        f"{server.server_name} (Version: {server.version})"
    )

    print(f"📦 Số lượng Tools công bố: {len(tools)}")

    # --------------------------------------------------------------------------
    # Kiểm tra danh sách Tools
    # --------------------------------------------------------------------------

    print("\n📋 DANH SÁCH TOOLS:")

    for tool in tools:
        print(f"   - {tool['name']}: {tool['description']}")

    # --------------------------------------------------------------------------
    # Test Tool 1: library_search
    # --------------------------------------------------------------------------

    print("\n🔎 TEST 1: library_search")

    test_result = server.call_tool(
        "library_search",
        {
            "document_id": "LIB001"
        }
    )

    print(
        json.dumps(
            test_result,
            ensure_ascii=False,
            indent=2
        )
    )

    # --------------------------------------------------------------------------
    # Test Tool 2: borrowed_documents
    # --------------------------------------------------------------------------

    print("\n📚 TEST 2: borrowed_documents")

    test_result = server.call_tool(
        "borrowed_documents",
        {
            "student_id": "SV2026001"
        }
    )

    print(
        json.dumps(
            test_result,
            ensure_ascii=False,
            indent=2
        )
    )

    # --------------------------------------------------------------------------
    # Test Tool 3: renew_document
    # --------------------------------------------------------------------------

    print("\n🔄 TEST 3: renew_document")

    test_result = server.call_tool(
        "renew_document",
        {
            "student_id": "SV2026001",
            "document_id": "LIB002"
        }
    )

    print(
        json.dumps(
            test_result,
            ensure_ascii=False,
            indent=2
        )
    )

    # --------------------------------------------------------------------------
    # Test NOT_FOUND
    # --------------------------------------------------------------------------

    print("\n⚠️ TEST 4: NOT_FOUND")

    test_result = server.call_tool(
        "library_search",
        {
            "document_id": "LIB9999999"
        }
    )

    print(
        json.dumps(
            test_result,
            ensure_ascii=False,
            indent=2
        )
    )

    print("\n==========================================================")
    print("✅ HOÀN TẤT KIỂM THỬ MCP SERVER")
    print("==========================================================")