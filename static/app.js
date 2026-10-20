// Giao diện phòng chat: nhận sự kiện qua WebSocket và hiển thị theo thời gian thực.

const $ = (id) => document.getElementById(id);
const messagesEl = $("messages");
const agentsEl = $("agents");
let ws;
let agents = {};
let running = false;

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (e) => handle(JSON.parse(e.data));
  ws.onclose = () => {
    setStatus(false, "Mất kết nối, đang thử lại…");
    setTimeout(connect, 1500);
  };
}

function handle(ev) {
  switch (ev.type) {
    case "state":
      renderAgents(ev.agents);
      $("mode").value = ev.settings.mode;
      $("max-turns").value = ev.settings.max_turns;
      messagesEl.innerHTML = "";
      ev.messages.forEach((m) => addMessage(m));
      setStatus(ev.running);
      break;
    case "message":
      addMessage(ev.message);
      break;
    case "agent_start":
      addMessage(ev.message, true);
      highlight(ev.message.speaker);
      break;
    case "delta": {
      const el = document.querySelector(`[data-id="${ev.id}"]`);
      if (el) {
        el.dataset.raw += ev.text;
        el.querySelector(".content").innerHTML = format(el.dataset.raw);
        scrollDown();
      }
      break;
    }
    case "agent_end": {
      const el = document.querySelector(`[data-id="${ev.id}"]`);
      if (el) el.classList.remove("streaming");
      highlight(null);
      break;
    }
    case "status":
      setStatus(ev.running);
      break;
  }
}

function renderAgents(list) {
  agents = {};
  agentsEl.innerHTML = "";
  list.forEach((a) => {
    agents[a.name] = a;
    const li = document.createElement("li");
    li.dataset.name = a.name;
    li.style.color = a.color;
    li.innerHTML = `
      <div class="avatar" style="background:${a.color}">${escapeHtml(a.name[0])}</div>
      <div>
        <div style="color:var(--text);font-weight:600">${escapeHtml(a.name)}</div>
        <div class="model">${escapeHtml(a.model)} · effort ${escapeHtml(a.effort)}</div>
        <div class="role">${escapeHtml(a.system.trim().split("\n")[0])}</div>
      </div>`;
    agentsEl.appendChild(li);
  });
}

function addMessage(m, streaming = false) {
  const el = document.createElement("div");
  el.className = `msg ${m.kind}` + (streaming ? " streaming" : "");
  el.dataset.id = m.id;
  el.dataset.raw = m.content;
  if (m.kind === "system") {
    el.innerHTML = `<div class="content">${escapeHtml(m.speaker)} · ${escapeHtml(m.content)}</div>`;
  } else {
    const color = m.kind === "user" ? "var(--accent)" : agents[m.speaker]?.color || "#64748b";
    const avatar = m.kind === "user" ? "" :
      `<div class="avatar" style="background:${color}">${escapeHtml(m.speaker[0])}</div>`;
    el.innerHTML = `${avatar}
      <div class="body">
        <div class="name" style="color:${color}">${escapeHtml(m.speaker)}</div>
        <div class="content">${format(m.content)}</div>
      </div>`;
  }
  messagesEl.appendChild(el);
  scrollDown();
}

function highlight(name) {
  agentsEl.querySelectorAll("li").forEach((li) =>
    li.classList.toggle("speaking", li.dataset.name === name));
}

function setStatus(isRunning, text) {
  running = isRunning;
  $("status-dot").classList.toggle("running", isRunning);
  $("status-text").textContent = text || (isRunning ? "Các agent đang làm việc…" : "Sẵn sàng");
  $("stop").disabled = !isRunning;
}

// Định dạng tối giản: khối ```code``` và `code` inline, phần còn lại giữ nguyên.
function format(text) {
  return escapeHtml(text)
    .replace(/```[\w-]*\n?([\s\S]*?)(```|$)/g, (_, code) => `<pre><code>${code}</code></pre>`)
    .replace(/`([^`\n]+)`/g, "<code>$1</code>");
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function scrollDown() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function send(payload) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(payload));
}

$("composer").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("input").value.trim();
  if (!text) return;
  send({ action: "send", text, mode: $("mode").value, max_turns: Number($("max-turns").value) });
  $("input").value = "";
});
$("input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("composer").requestSubmit();
  }
});
$("stop").addEventListener("click", () => send({ action: "stop" }));
$("reset").addEventListener("click", () => {
  if (confirm("Xóa toàn bộ cuộc trò chuyện?")) send({ action: "reset" });
});

connect();
