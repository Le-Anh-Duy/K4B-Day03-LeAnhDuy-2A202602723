/*
 * 🤖 REACT AGENT WEB UI — Trợ lý Quản lý Thư viện & Tài liệu (VinUni Day 03 Lab)
 *
 * React 18 chạy trực tiếp từ thư mục vendor/ (không cần npm, không cần build step).
 * JSX được thay bằng htm — cú pháp template literal gần như y hệt JSX.
 */

const { useState, useEffect, useRef, useCallback, useMemo } = React;
const html = htm.bind(React.createElement);

/* ========================================================================== */
/* HELPERS                                                                     */
/* ========================================================================== */

const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);

const pretty = (value) => JSON.stringify(value, null, 2);

function timeLabel(ts) {
  return new Date(ts).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

/** Gán màu cho từng dòng console log dựa trên emoji mà Agent in ra. */
function logClass(line) {
  if (line.includes("🧠")) return "l-thought";
  if (line.includes("🛠️")) return "l-action";
  if (line.includes("👁️")) return "l-obs";
  if (line.includes("🏁")) return "l-final";
  if (line.includes("⚠️")) return "l-warn";
  if (line.includes("🔄") || line.startsWith("---")) return "l-loop";
  return "";
}

const ACTION_META = {
  TOOL_EXECUTION: { icon: "🛠️", label: "Tool Execution", cls: "tool" },
  FINAL_ANSWER: { icon: "🏁", label: "Final Answer", cls: "final" },
  EXECUTION_ERROR: { icon: "⚠️", label: "Execution Error", cls: "error" },
  MAX_ITERATIONS_REACHED: { icon: "⏱️", label: "Max Iterations", cls: "warn" },
};

const actionMeta = (type) =>
  ACTION_META[type] || { icon: "•", label: type || "Unknown", cls: "" };

/** Đọc luồng SSE do /api/chat trả về và bắn từng event ra ngoài. */
async function streamChat(message, onEvent) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok || !res.body) throw new Error("HTTP " + res.status);

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let split;
    while ((split = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);

      let event = "message";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (data) onEvent(event, JSON.parse(data));
    }
  }
}

/* ========================================================================== */
/* SHARED COMPONENTS                                                           */
/* ========================================================================== */

function TraceStep({ entry, maxLatency }) {
  const meta = actionMeta(entry.action_type);
  const width = maxLatency > 0 ? Math.max(2, (entry.latency_ms / maxLatency) * 100) : 0;

  return html`
    <div className="step">
      <div className="step-head">
        <span className="pill step">Step ${entry.step}</span>
        <span className=${"pill " + meta.cls}>${meta.icon} ${meta.label}</span>
        ${entry.tool_name && html`<span className="pill tool">${entry.tool_name}</span>`}
        <span className="pill lat">${entry.latency_ms} ms</span>
      </div>
      <div className="step-body">
        ${entry.thought && html`
          <div>
            <div className="field-label thought">🧠 Thought</div>
            <div>${entry.thought}</div>
          </div>`}

        ${entry.arguments && html`
          <div>
            <div className="field-label action">🛠️ Action — arguments</div>
            <pre className="code">${pretty(entry.arguments)}</pre>
          </div>`}

        ${entry.observation && html`
          <div>
            <div className="field-label obs">👁️ Observation (MCP Server)</div>
            <pre className="code">${pretty(entry.observation)}</pre>
          </div>`}

        ${entry.output && html`
          <div>
            <div className="field-label">🏁 Output</div>
            <div>${entry.output}</div>
          </div>`}

        ${maxLatency > 0 && html`
          <div className="bar-track"><div className="bar-fill" style=${{ width: width + "%" }}></div></div>`}
      </div>
    </div>`;
}

function TraceList({ trace }) {
  if (!trace || !trace.length) {
    return html`<div className="muted-note">Chưa có trace nào. Hãy gửi một câu hỏi để xem vòng lặp ReAct.</div>`;
  }
  const maxLatency = Math.max(...trace.map((t) => t.latency_ms || 0));
  return html`<div>
    ${trace.map((entry, i) => html`<${TraceStep} key=${i} entry=${entry} maxLatency=${maxLatency} />`)}
  </div>`;
}

function LogView({ lines, autoScroll, style }) {
  const ref = useRef(null);
  useEffect(() => {
    if (autoScroll && ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [lines, autoScroll]);

  if (!lines || !lines.length) {
    return html`<div className="muted-note">Chưa có log nào.</div>`;
  }
  return html`
    <div className="logs" ref=${ref} style=${style}>
      ${lines.map((line, i) => html`<div key=${i} className=${logClass(line)}>${line || " "}</div>`)}
    </div>`;
}

/* ========================================================================== */
/* INSPECTOR (PANEL PHẢI)                                                      */
/* ========================================================================== */

function ToolCard({ tool }) {
  const props = (tool.parameters && tool.parameters.properties) || {};
  const required = (tool.parameters && tool.parameters.required) || [];
  const names = Object.keys(props);

  return html`
    <details className="tool-card">
      <summary>
        <span>🛠️</span>
        <span className="name">${tool.name}</span>
        <span className="count">${names.length} tham số</span>
      </summary>
      <div className="desc">${tool.description}</div>
      <div className="params">
        ${names.map((name) => html`
          <div className="param" key=${name}>
            <span className="pname">${name}</span>
            <span className="ptype">${props[name].type}</span>
            ${required.includes(name) && html`<span className="preq">bắt buộc</span>`}
            <div className="pdesc">${props[name].description}</div>
          </div>`)}
      </div>
    </details>`;
}

function Inspector({ meta, tab, setTab, trace, logs, running }) {
  const tabs = [
    ["tools", "🛠️ Tools" + (meta ? " (" + meta.tools.length + ")" : "")],
    ["trace", "📊 Trace" + (trace.length ? " (" + trace.length + ")" : "")],
    ["logs", "📜 Logs" + (logs.length ? " (" + logs.length + ")" : "")],
    ["prompt", "🧠 Prompt"],
  ];

  return html`
    <${React.Fragment}>
      <div className="pane-head">
        Inspector
        <span className="spacer"></span>
        ${running && html`<span className="spinner"></span>`}
      </div>

      <div className="tabs">
        ${tabs.map(([key, label]) => html`
          <button key=${key} className=${tab === key ? "on" : ""} onClick=${() => setTab(key)}>${label}</button>`)}
      </div>

      <div className="pane-scroll">
        ${tab === "tools" && html`
          <div>
            <div className="muted-note" style=${{ padding: "0 0 10px", textAlign: "left" }}>
              Tools được MCP Server <b>${meta ? meta.mcp_server : "..."}</b> công bố qua <code>list_tools()</code>.
            </div>
            ${meta ? meta.tools.map((t) => html`<${ToolCard} key=${t.name} tool=${t} />`)
                   : html`<div className="muted-note">Đang tải...</div>`}
          </div>`}

        ${tab === "trace" && html`<${TraceList} trace=${trace} />`}

        ${tab === "logs" && html`
          <${LogView} lines=${logs} autoScroll=${running} style=${{ maxHeight: "none" }} />`}

        ${tab === "prompt" && html`
          <pre className="code" style=${{ maxHeight: "none" }}>
${meta ? meta.system_prompt : "Đang tải..."}</pre>`}
      </div>
    </${React.Fragment}>`;
}

/* ========================================================================== */
/* CHAT                                                                        */
/* ========================================================================== */

function Message({ msg }) {
  const isUser = msg.role === "user";
  return html`
    <div className=${"msg " + msg.role}>
      <div className="avatar">${isUser ? "👤" : "🤖"}</div>
      <div className="content">
        <div className="who">
          ${isUser ? "Sinh viên" : "ReAct Agent"}
          ${msg.ts && html` · ${timeLabel(msg.ts)}`}
          ${msg.durationMs != null && html` · ${(msg.durationMs / 1000).toFixed(2)}s`}
        </div>
        <div className="bubble">${msg.content || "(không có nội dung trả lời)"}</div>

        ${!isUser && msg.trace && msg.trace.length > 0 && html`
          <details className="disclosure">
            <summary>📊 Trace — ${msg.trace.length} sự kiện ReAct</summary>
            <div className="inner"><${TraceList} trace=${msg.trace} /></div>
          </details>`}

        ${!isUser && msg.logs && msg.logs.length > 0 && html`
          <details className="disclosure">
            <summary>📜 Console log — ${msg.logs.length} dòng</summary>
            <div className="inner">
              <${LogView} lines=${msg.logs} autoScroll=${false} style=${{ maxHeight: "300px" }} />
            </div>
          </details>`}
      </div>
    </div>`;
}

function LiveMessage({ trace, logs }) {
  return html`
    <div className="msg assistant">
      <div className="avatar">🤖</div>
      <div className="content">
        <div className="who">ReAct Agent · <span className="spinner"></span> đang suy luận...</div>
        ${trace.length > 0
          ? html`<${TraceList} trace=${trace} />`
          : html`<div className="bubble">Đang gửi yêu cầu tới LLM Provider...</div>`}
        ${logs.length > 0 && html`
          <details className="disclosure" open>
            <summary>📜 Console log trực tiếp</summary>
            <div className="inner">
              <${LogView} lines=${logs} autoScroll=${true} style=${{ maxHeight: "220px" }} />
            </div>
          </details>`}
      </div>
    </div>`;
}

function EmptyState({ meta, onPick }) {
  return html`
    <div className="empty">
      <h2>🤖 ReAct Agent — Trợ lý Thư viện VinUni</h2>
      <div>
        Agent suy luận theo vòng lặp <b>Thought → Action → Observation</b> và gọi Tool qua MCP Server.
        Mọi bước đều hiện ở panel Inspector bên phải.
      </div>
      ${meta && meta.test_cases.length > 0 && html`
        <div className="chips">
          ${meta.test_cases.map((tc) => html`
            <button className="chip" key=${tc.id} onClick=${() => onPick(tc.question)}>
              <span className="tag">${tc.id} · ${tc.type} · ${tc.complexity}</span>
              ${tc.question}
            </button>`)}
        </div>`}
    </div>`;
}

function Composer({ value, setValue, onSend, running, maxIterations }) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [value]);

  const keyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return html`
    <div className="composer">
      <div className="composer-inner">
        <textarea
          ref=${ref}
          value=${value}
          placeholder=${running ? "Agent đang xử lý..." : "Hỏi trợ lý thư viện... (Enter để gửi, Shift+Enter xuống dòng)"}
          disabled=${running}
          onChange=${(e) => setValue(e.target.value)}
          onKeyDown=${keyDown}
        ></textarea>
        <button className="send" onClick=${onSend} disabled=${running || !value.trim()}>
          ${running ? "Đang chạy..." : "Gửi ▸"}
        </button>
      </div>
      <div className="hint">
        Mỗi câu hỏi là một phiên ReAct độc lập, tối đa ${maxIterations || "?"} vòng lặp — giống hệt
        <code> python src/app.py --interactive</code>.
      </div>
    </div>`;
}

/* ========================================================================== */
/* APP                                                                         */
/* ========================================================================== */

function App() {
  const [meta, setMeta] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [draft, setDraft] = useState("");
  const [running, setRunning] = useState(false);
  const [liveTrace, setLiveTrace] = useState([]);
  const [liveLogs, setLiveLogs] = useState([]);
  const [showLeft, setShowLeft] = useState(true);
  const [showRight, setShowRight] = useState(true);
  const [tab, setTab] = useState("tools");

  const loadedRef = useRef(false);
  const messagesRef = useRef(null);

  /* ------------------------------------------------------------ tải dữ liệu */

  useEffect(() => {
    fetch("/api/meta").then((r) => r.json()).then(setMeta).catch(() => setMeta(null));

    fetch("/api/history")
      .then((r) => r.json())
      .then((data) => {
        const list = (data && data.sessions) || [];
        setSessions(list);
        if (list.length) setActiveId(list[0].id);
      })
      .catch(() => {})
      .finally(() => { loadedRef.current = true; });
  }, []);

  /* --------------------------------------------- tự động lưu lịch sử chat */

  useEffect(() => {
    if (!loadedRef.current) return;
    const timer = setTimeout(() => {
      fetch("/api/history", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessions }),
      }).catch(() => {});
    }, 400);
    return () => clearTimeout(timer);
  }, [sessions]);

  const active = useMemo(
    () => sessions.find((s) => s.id === activeId) || null,
    [sessions, activeId]
  );
  const messages = active ? active.messages : [];

  /* ------------------------------------------------------------ auto scroll */

  useEffect(() => {
    const el = messagesRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, liveTrace, liveLogs]);

  /* ----------------------------------------------------------- thao tác chat */

  const patchSession = useCallback((id, updater) => {
    setSessions((prev) => prev.map((s) => (s.id === id ? updater(s) : s)));
  }, []);

  const newChat = useCallback(() => {
    const session = { id: uid(), title: "Cuộc trò chuyện mới", createdAt: Date.now(), messages: [] };
    setSessions((prev) => [session, ...prev]);
    setActiveId(session.id);
    return session.id;
  }, []);

  const deleteChat = useCallback((id, e) => {
    e.stopPropagation();
    setSessions((prev) => {
      const next = prev.filter((s) => s.id !== id);
      setActiveId((cur) => (cur === id ? (next[0] ? next[0].id : null) : cur));
      return next;
    });
  }, []);

  const send = useCallback(async () => {
    const text = draft.trim();
    if (!text || running) return;

    let sessionId = activeId;
    if (!sessionId) sessionId = newChat();

    setDraft("");
    setRunning(true);
    setLiveTrace([]);
    setLiveLogs([]);
    setTab("trace");

    patchSession(sessionId, (s) => ({
      ...s,
      title: s.messages.length === 0 ? text.slice(0, 48) : s.title,
      messages: [...s.messages, { role: "user", content: text, ts: Date.now() }],
    }));

    const collectedTrace = [];
    const collectedLogs = [];

    try {
      await streamChat(text, (event, data) => {
        if (event === "log") {
          collectedLogs.push(data.line);
          setLiveLogs([...collectedLogs]);
        } else if (event === "trace") {
          collectedTrace.push(data);
          setLiveTrace([...collectedTrace]);
        } else if (event === "error") {
          collectedLogs.push("⚠️ [SERVER ERROR]: " + data.message);
          setLiveLogs([...collectedLogs]);
        } else if (event === "done") {
          patchSession(sessionId, (s) => ({
            ...s,
            messages: [...s.messages, {
              role: "assistant",
              content: data.answer,
              trace: data.trace.length ? data.trace : collectedTrace,
              logs: collectedLogs.slice(),
              durationMs: data.duration_ms,
              ts: Date.now(),
            }],
          }));
        }
      });
    } catch (err) {
      patchSession(sessionId, (s) => ({
        ...s,
        messages: [...s.messages, {
          role: "assistant",
          content: "⚠️ Không kết nối được tới server: " + err.message,
          logs: collectedLogs.slice(),
          ts: Date.now(),
        }],
      }));
    } finally {
      setRunning(false);
      setLiveTrace([]);
      setLiveLogs([]);
    }
  }, [draft, running, activeId, newChat, patchSession]);

  /* --------------------------------- dữ liệu hiển thị cho panel Inspector */

  const lastAssistant = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return messages[i];
    }
    return null;
  }, [messages]);

  const inspectorTrace = running ? liveTrace : (lastAssistant && lastAssistant.trace) || [];
  const inspectorLogs = running ? liveLogs : (lastAssistant && lastAssistant.logs) || [];

  const isMock = meta && meta.provider === "MockOfflineProvider";

  /* ----------------------------------------------------------------- render */

  return html`
    <div className="app">
      <header className="top">
        <div className="brand">
          <span className="logo">📚</span>
          <div>
            ReAct Agent — Trợ lý Thư viện
            <small>VinUni AI Course · Day 03 Lab</small>
          </div>
        </div>

        <div className="badges">
          ${meta && html`
            <${React.Fragment}>
              <span className="badge">
                <span className=${"dot" + (isMock ? " off" : "")}></span>
                LLM: <b>${meta.provider.replace("Provider", "")}</b> · ${meta.model}
              </span>
              <span className="badge">MCP: <b>${meta.mcp_server}</b> v${meta.mcp_version}</span>
              <span className="badge">Tools: <b>${meta.tools.length}</b></span>
              <span className="badge">Max loop: <b>${meta.max_iterations}</b></span>
            </${React.Fragment}>`}
        </div>

        <div className="toggles">
          <button className=${showLeft ? "on" : ""} onClick=${() => setShowLeft((v) => !v)}>
            ☰ Lịch sử
          </button>
          <button className=${showRight ? "on" : ""} onClick=${() => setShowRight((v) => !v)}>
            🔍 Inspector
          </button>
        </div>
      </header>

      <div className="body-grid"
           style=${{ "--left": showLeft ? "260px" : "0px", "--right": showRight ? "380px" : "0px" }}>

        <aside className=${"left" + (showLeft ? " float" : " hidden")}>
          <button className="btn-new" onClick=${newChat}>＋ Cuộc trò chuyện mới</button>
          <div className="pane-head">Lịch sử (${sessions.length})</div>
          <div className="session-list">
            ${sessions.length === 0
              ? html`<div className="muted-note">Chưa có cuộc trò chuyện nào.</div>`
              : sessions.map((s) => html`
                  <div key=${s.id}
                       className=${"session" + (s.id === activeId ? " active" : "")}
                       onClick=${() => setActiveId(s.id)}>
                    <div className="title">
                      ${s.title}
                      <div className="meta">${s.messages.length} tin nhắn · ${timeLabel(s.createdAt)}</div>
                    </div>
                    <button className="del" title="Xoá" onClick=${(e) => deleteChat(s.id, e)}>✕</button>
                  </div>`)}
          </div>
        </aside>

        <main className="chat">
          <div className="messages" ref=${messagesRef}>
            ${messages.length === 0 && !running
              ? html`<${EmptyState} meta=${meta} onPick=${(q) => setDraft(q)} />`
              : messages.map((m, i) => html`<${Message} key=${i} msg=${m} />`)}
            ${running && html`<${LiveMessage} trace=${liveTrace} logs=${liveLogs} />`}
          </div>

          <${Composer}
            value=${draft}
            setValue=${setDraft}
            onSend=${send}
            running=${running}
            maxIterations=${meta && meta.max_iterations} />
        </main>

        <aside className=${"right" + (showRight ? " float" : " hidden")}>
          <${Inspector}
            meta=${meta}
            tab=${tab}
            setTab=${setTab}
            trace=${inspectorTrace}
            logs=${inspectorLogs}
            running=${running} />
        </aside>
      </div>
    </div>`;
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${App} />`);
