/**
 * Rule-Based & NLP Hybrid Chatbot - Embeddable Web Widget
 * Usage: <script src="http://localhost:8000/static/widget.js" data-api-url="http://localhost:8000"></script>
 */

(function () {
  const currentScript = document.currentScript;
  const API_BASE = (currentScript && currentScript.getAttribute('data-api-url')) || window.location.origin;
  const API_KEY = (currentScript && currentScript.getAttribute('data-api-key')) || '';
  const SESSION_ID = 'widget_' + Math.random().toString(36).substring(2, 9);

  // Inject Styles
  const style = document.createElement('style');
  style.innerHTML = `
    .agy-chat-bubble-btn {
      position: fixed;
      bottom: 24px;
      right: 24px;
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: linear-gradient(135deg, #1e88e5, #1565c0);
      color: #fff;
      border: none;
      box-shadow: 0 4px 16px rgba(0,0,0,0.2);
      cursor: pointer;
      z-index: 999999;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 28px;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .agy-chat-bubble-btn:hover {
      transform: scale(1.08);
      box-shadow: 0 6px 20px rgba(30,136,229,0.4);
    }
    .agy-chat-window {
      position: fixed;
      bottom: 96px;
      right: 24px;
      width: 380px;
      max-width: calc(100vw - 32px);
      height: 540px;
      max-height: calc(100vh - 120px);
      background: #ffffff;
      border-radius: 16px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.15);
      z-index: 999999;
      display: none;
      flex-direction: column;
      overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      border: 1px solid #e0e0e0;
      animation: agyFadeIn 0.25s ease-out;
    }
    @keyframes agyFadeIn {
      from { opacity: 0; transform: translateY(12px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .agy-chat-header {
      background: linear-gradient(135deg, #1e88e5, #0d47a1);
      color: white;
      padding: 14px 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-weight: 600;
    }
    .agy-chat-header-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 15px;
    }
    .agy-chat-close-btn {
      background: none;
      border: none;
      color: white;
      font-size: 20px;
      cursor: pointer;
      opacity: 0.85;
    }
    .agy-chat-close-btn:hover { opacity: 1; }
    .agy-chat-body {
      flex: 1;
      padding: 16px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 12px;
      background: #f8fafc;
    }
    .agy-msg {
      max-width: 82%;
      padding: 10px 14px;
      border-radius: 14px;
      font-size: 14px;
      line-height: 1.45;
      word-wrap: break-word;
      white-space: pre-wrap;
    }
    .agy-msg-bot {
      align-self: flex-start;
      background: #ffffff;
      color: #1e293b;
      border: 1px solid #e2e8f0;
      border-bottom-left-radius: 2px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .agy-msg-user {
      align-self: flex-end;
      background: #1e88e5;
      color: #ffffff;
      border-bottom-right-radius: 2px;
    }
    .agy-quick-pills {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      padding: 6px 16px;
      background: #f8fafc;
      border-top: 1px solid #eef2f6;
    }
    .agy-pill {
      background: #e3f2fd;
      color: #0d47a1;
      border: none;
      border-radius: 12px;
      padding: 4px 10px;
      font-size: 12px;
      cursor: pointer;
      transition: background 0.15s;
    }
    .agy-pill:hover { background: #bbdefb; }
    .agy-chat-input-area {
      display: flex;
      padding: 10px 12px;
      border-top: 1px solid #e2e8f0;
      background: #ffffff;
      gap: 8px;
    }
    .agy-chat-input {
      flex: 1;
      border: 1px solid #cbd5e1;
      border-radius: 20px;
      padding: 8px 14px;
      font-size: 14px;
      outline: none;
    }
    .agy-chat-input:focus { border-color: #1e88e5; }
    .agy-chat-send {
      background: #1e88e5;
      color: white;
      border: none;
      border-radius: 50%;
      width: 36px;
      height: 36px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
    }
    .agy-chat-send:hover { background: #1565c0; }
  `;
  document.head.appendChild(style);

  // Inject HTML Elements
  const container = document.createElement('div');
  container.innerHTML = `
    <button class="agy-chat-bubble-btn" id="agyBubbleBtn" title="Chat with us">💬</button>
    <div class="agy-chat-window" id="agyChatWindow">
      <div class="agy-chat-header">
        <div class="agy-chat-header-title">
          <span>🤖</span>
          <span>Assistant</span>
        </div>
        <button class="agy-chat-close-btn" id="agyCloseBtn">&times;</button>
      </div>
      <div class="agy-chat-body" id="agyChatBody">
        <div class="agy-msg agy-msg-bot">👋 Hello! How can I assist you today? You can ask about our opening hours, location, pricing, or book an appointment!</div>
      </div>
      <div class="agy-quick-pills">
        <button class="agy-pill" data-text="What are your hours?">🕒 Hours</button>
        <button class="agy-pill" data-text="Book a table for 2 tomorrow at 7pm">📅 Book Table</button>
        <button class="agy-pill" data-text="Pricing details">💲 Pricing</button>
      </div>
      <div class="agy-chat-input-area">
        <input type="text" class="agy-chat-input" id="agyChatInput" placeholder="Type a message..." autocomplete="off" />
        <button class="agy-chat-send" id="agySendBtn">➤</button>
      </div>
    </div>
  `;
  document.body.appendChild(container);

  // References
  const bubbleBtn = document.getElementById('agyBubbleBtn');
  const chatWindow = document.getElementById('agyChatWindow');
  const closeBtn = document.getElementById('agyCloseBtn');
  const chatBody = document.getElementById('agyChatBody');
  const chatInput = document.getElementById('agyChatInput');
  const sendBtn = document.getElementById('agySendBtn');

  // Toggle Visibility
  bubbleBtn.addEventListener('click', () => {
    const isHidden = chatWindow.style.display === 'none' || !chatWindow.style.display;
    chatWindow.style.display = isHidden ? 'flex' : 'none';
    if (isHidden) chatInput.focus();
  });
  closeBtn.addEventListener('click', () => {
    chatWindow.style.display = 'none';
  });

  // Append message to UI
  function appendMessage(text, isUser = false) {
    const msg = document.createElement('div');
    msg.className = `agy-msg ${isUser ? 'agy-msg-user' : 'agy-msg-bot'}`;
    msg.textContent = text;
    chatBody.appendChild(msg);
    chatBody.scrollTop = chatBody.scrollHeight;
  }

  // Send message to API
  async function sendMessage(text) {
    const userMsg = text.trim();
    if (!userMsg) return;

    appendMessage(userMsg, true);
    chatInput.value = '';

    try {
      const headers = { 'Content-Type': 'application/json' };
      if (API_KEY) headers['X-API-Key'] = API_KEY;

      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
          message: userMsg,
          session_id: SESSION_ID
        })
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Service temporarily unavailable.' }));
        appendMessage(`⚠️ Error (${res.status}): ${err.detail || 'Failed to get response.'}`);
        return;
      }

      const data = await res.json();
      appendMessage(data.response);
    } catch (err) {
      appendMessage("⚠️ Connection error. Please check backend server status.");
    }
  }

  sendBtn.addEventListener('click', () => sendMessage(chatInput.value));
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendMessage(chatInput.value);
  });

  // Pill suggestions click
  document.querySelectorAll('.agy-pill').forEach(pill => {
    pill.addEventListener('click', (e) => {
      const text = e.target.getAttribute('data-text');
      if (text) sendMessage(text);
    });
  });
})();
