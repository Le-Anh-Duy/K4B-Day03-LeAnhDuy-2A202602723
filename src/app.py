"""
🚀 CORE AGENT APPLICATION (DAY 03: CHATBOT VS REACT AGENT)
Thực thi so sánh giữa Chatbot Baseline (Cấp 2) và ReAct Agent kết nối MCP Server (Cấp 3).
"""
import json
import os
import sys
import time
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from mcp_server import MCPLibraryServer
from prompts import CHATBOT_BASELINE_PROMPT, REACT_AGENT_SYSTEM_PROMPT, MAX_ITERATIONS
from providers import get_llm_provider

load_dotenv()

def load_test_cases():
    """Tải danh sách test cases từ config/test_cases.json."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")
    if not os.path.exists(config_path):
        example_path = os.path.join(base_dir, "config", "test_cases.example.json")
        if os.path.exists(example_path):
            print("⚠️ [CONFIG NOTICE]: Chưa thấy 'config/test_cases.json'. Đang dùng file mẫu.")
            print("👉 Hãy copy test_cases.example.json thành test_cases.json và viết test cases.\n")
            config_path = example_path
        else:
            config_path = "test_cases.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_waterfall_trace(trace_data: list):
    """Ghi Waterfall Trace Log ra docs/trace_waterfall.json."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(base_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    trace_path = os.path.join(docs_dir, "trace_waterfall.json")
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(trace_data, f, ensure_ascii=False, indent=2)
    print(f"📊 [OBSERVABILITY]: Đã lưu {len(trace_data)} sự kiện tại '{trace_path}'!")

def run_baseline_chatbot(user_query: str, provider):
    """Chạy Chatbot Baseline (Cấp 2) không có Tool."""
    print(f"\n💬 [CHATBOT BASELINE] Câu hỏi: {user_query}")
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT)
    print(f"🤖 Chatbot phản hồi:\n{response}")

def run_react_agent(user_query: str, provider, mcp_server: MCPLibraryServer, on_event=None) -> list:
    """Thực thi ReAct: Thought -> Action -> Observation -> tiếp tục hoặc Final Answer."""
    print(f"\n🤖 [REACT AGENT] Câu hỏi: {user_query}")
    step = 0
    trace_logs = []

    def log_trace(entry: dict):
        """Ghi 1 trace event vào log, đồng thời đẩy ra ngoài qua on_event (nếu có).

        on_event chỉ được Web UI truyền vào để stream trace theo thời gian thực.
        Ở chế độ CLI, on_event = None nên hành vi giữ nguyên như cũ.
        """
        trace_logs.append(entry)
        if on_event:
            on_event(entry)

    observations = []
    tools_list = mcp_server.list_tools()

    while step < MAX_ITERATIONS:
        step += 1
        step_start_time = time.time()
        print(f"\n--- 🔄 Vòng lặp ReAct Loop (Step {step}/{MAX_ITERATIONS}) ---")

        if observations:
            observation_context = "\n\nKẾT QUẢ CÁC TOOL ĐÃ THỰC THI:\n" + "\n".join(
                f"- Tool: {obs['tool_name']}\n"
                f"  Arguments: {json.dumps(obs['arguments'], ensure_ascii=False)}\n"
                f"  Observation: {json.dumps(obs['result'], ensure_ascii=False)}"
                for obs in observations
            )
        else:
            observation_context = ""

        current_query = (
            f"{user_query}"
            f"{observation_context}\n\n"
            "Hãy tiếp tục suy luận dựa trên các Observation ở trên. "
            "Nếu đã đủ thông tin thì trả lời người dùng. "
            "Nếu cần thêm dữ liệu thì tiếp tục gọi Tool phù hợp."
        )

        llm_response = provider.generate_with_tools(
            current_query,
            tools_list,
            system_prompt=REACT_AGENT_SYSTEM_PROMPT
        )
        latency_ms = round((time.time() - step_start_time) * 1000, 2)
        thought = llm_response.get("thought", "Đang suy luận...")
        print(f"🧠 [Thought]: {thought}")

        if llm_response.get("type") == "text":
            final_content = llm_response.get("content", "")
            print(f"🏁 [Final Answer]: {final_content}")
            log_trace({
                "step": step,
                "query": user_query,
                "action_type": "FINAL_ANSWER",
                "thought": thought,
                "output": final_content,
                "latency_ms": latency_ms
            })
            break

        if llm_response.get("type") == "tool_call":
            tool_name = llm_response.get("tool_name")
            arguments = llm_response.get("arguments", {})
            print(f"🛠️ [Action Proposed]: {tool_name}({arguments})")

            mcp_result = mcp_server.call_tool(tool_name, arguments)
            obs_data = mcp_result.get("result", {})

            if not obs_data:
                obs_data = {
                    "status": "EXECUTION_ERROR",
                    "message": "Không nhận được dữ liệu từ MCP Server."
                }

            obs_str = json.dumps(obs_data, ensure_ascii=False)
            print(f"👁️ [Observation từ MCP Server]: {obs_str}")

            observations.append({
                "tool_name": tool_name,
                "arguments": arguments,
                "result": obs_data
            })

            log_trace({
                "step": step,
                "query": user_query,
                "action_type": "TOOL_EXECUTION",
                "tool_name": tool_name,
                "arguments": arguments,
                "observation": obs_data,
                "latency_ms": latency_ms
            })

            # Không break: cho phép ReAct gọi Tool tiếp theo ở bước kế tiếp.
            continue

        print("⚠️ [REACT AGENT]: LLM trả về loại response không hợp lệ.")
        log_trace({
            "step": step,
            "query": user_query,
            "action_type": "EXECUTION_ERROR",
            "output": "LLM trả về response không hợp lệ.",
            "latency_ms": latency_ms
        })
        break

    if step >= MAX_ITERATIONS:
        print("\n⚠️ [REACT AGENT] Đã đạt giới hạn số vòng lặp.")
        log_trace({
            "step": step + 1,
            "query": user_query,
            "action_type": "MAX_ITERATIONS_REACHED",
            "thought": "Agent đạt giới hạn số vòng lặp.",
            "output": "Xin lỗi, tôi chưa thể hoàn tất yêu cầu trong số bước xử lý cho phép.",
            "latency_ms": 0
        })

    return trace_logs

if __name__ == "__main__":
    print("==========================================================")
    print("🏫 VINUNI AI COURSE - DAY 03 LAB: CHATBOT VS REACT AGENT")
    print("==========================================================")

    provider = get_llm_provider()
    mcp_server = MCPLibraryServer()

    print(f"🔌 LLM Provider: {provider.__class__.__name__}")
    print(f"🌐 MCP Server: {mcp_server.server_name}\n")

    tests = load_test_cases()
    print(f"✅ Đã tải thành công {len(tests)} Test Cases thử nghiệm.\n")

    if "--interactive" in sys.argv:
        print("🎮 [INTERACTIVE MODE] Trò chuyện trực tiếp với ReAct Agent:")
        print("💡 Gợi ý câu hỏi:")
        print("   - 'Tìm vị trí cuốn Introduction to Computer Science'")
        print("   - 'Tôi là sinh viên SV2026001, hãy cho tôi biết các tài liệu đang mượn'")
        print("   - 'Tôi là SV2026001, kiểm tra hạn trả Database System Concepts và gia hạn nếu đủ điều kiện'")
        print("   - Gõ 'exit' hoặc 'quit' để kết thúc.\n")

        while True:
            try:
                user_input = input("👤 Sinh viên hỏi: ").strip()
                if not user_input or user_input.lower() in ["exit", "quit"]:
                    print("👋 Tạm biệt! Kết thúc phiên trò chuyện.")
                    break
                logs = run_react_agent(user_input, provider, mcp_server)
                save_waterfall_trace(logs)
            except (KeyboardInterrupt, EOFError):
                print("\n👋 Đã thoát phiên tương tác.")
                break

    elif "--all" in sys.argv:
        print("🚀 [TEST SUITE MODE] Kiểm tra 5 Test Cases:")
        completed_count = 0
        todo_count = 0
        all_traces = []

        for tc in tests:
            print("\n==================================================")
            print(f"🧪 [{tc['id']}] Loại test: {tc['type']} (Độ phức tạp: {tc['complexity']})")
            print(f"📌 Kỳ vọng: {tc['expected_behavior']}")

            if tc["question"].strip().startswith("TODO"):
                print("⏸️ [CHƯA KÍCH HOẠT - ĐANG LÀ TODO]:")
                print(f"   {tc['question']}")
                print("   👉 Hãy mở file 'config/test_cases.json' để viết câu hỏi thực tế!")
                todo_count += 1
            else:
                logs = run_react_agent(tc["question"], provider, mcp_server)
                all_traces.extend(logs)
                completed_count += 1

        print("\n==================================================")
        print(
            f"📊 [KẾT QUẢ TEST SUITE]: Đã thực thi "
            f"{completed_count}/{len(tests)} Test Cases | "
            f"{todo_count} Test Cases đang chờ điền câu hỏi (TODO)"
        )

        if all_traces:
            save_waterfall_trace(all_traces)

        print("💡 Để trò chuyện trực tiếp: python src/app.py --interactive")

    else:
        print("ℹ️ HƯỚNG DẪN SỬ DỤNG:")
        print("  1. Chat trực tiếp:       python src/app.py --interactive")
        print("  2. Chạy toàn bộ Test:    python src/app.py --all\n")

        sample_query = tests[1]["question"]
        print("--- 🏁 DEMO CHẠY THỬ 1 TEST CASE MẪU (TC02: Tra cứu tài liệu) ---")
        logs = run_react_agent(sample_query, provider, mcp_server)
        save_waterfall_trace(logs)
        print("\n💡 Hãy thử: python src/app.py --interactive")

