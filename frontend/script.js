/* ─── DOM refs ─── */
const textarea    = document.getElementById('user-input');
const sendBtn     = document.getElementById('send-btn');
const chatArea    = document.getElementById('chat-area');
const chatScroll  = document.getElementById('chat-scroll');
const chatMsgs    = document.getElementById('chat-messages');
const welcome     = document.getElementById('welcome');
const waitTooltip = document.getElementById('wait-tooltip');

/* ─── State ─── */
let isProcessing  = false;
let typeTimer     = null;
let tooltipTimer  = null;
let chatActivated = false;

/* ─── Auto-resize textarea ─── */
textarea.addEventListener('input', () => {
  textarea.style.height = 'auto';
  textarea.style.height = Math.min(textarea.scrollHeight, 160) + 'px';
  updateSendState();
});

/* ─── Keydown: Enter sends OR shows tooltip during processing ─── */
textarea.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (isProcessing) { showWaitTooltip(); return; }
    if (!sendBtn.disabled) handleSend();
  }
});

/* ─── Button click ─── */
sendBtn.addEventListener('click', () => {
  if (isProcessing) stopResponse();
  else handleSend();
});

/* ─── Update button state ─── */
function updateSendState() {
  if (isProcessing) {
    sendBtn.disabled = false;
    sendBtn.classList.add('processing');
  } else {
    sendBtn.disabled = textarea.value.trim().length === 0;
    sendBtn.classList.remove('processing');
  }
}

/* ─── Tooltip ─── */
function showWaitTooltip() {
  clearTimeout(tooltipTimer);
  waitTooltip.classList.add('show');
  tooltipTimer = setTimeout(() => waitTooltip.classList.remove('show'), 2500);
}

/* ─── Activate chat (hide welcome) ─── */
function activateChat() {
  if (chatActivated) return;
  chatActivated = true;
  welcome.classList.add('hidden');
  chatArea.classList.add('active');
  setTimeout(() => { welcome.style.display = 'none'; }, 500);
}

/* ─── Avatar SVG ─── */
function avatarSVG() {
  return `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="#888" stroke-width="1.7" stroke-linejoin="round" stroke-linecap="round"/>
    <path d="M2 17l10 5 10-5" stroke="#888" stroke-width="1.7" stroke-linejoin="round" stroke-linecap="round"/>
    <path d="M2 12l10 5 10-5" stroke="#555" stroke-width="1.7" stroke-linejoin="round" stroke-linecap="round"/>
  </svg>`;
}

/* ─── Append user message ─── */
function appendUserMessage(text) {
  const wrap   = document.createElement('div');
  wrap.className = 'content-wrap';

  const row    = document.createElement('div');
  row.className = 'msg-row user';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;

  row.appendChild(bubble);
  wrap.appendChild(row);
  chatMsgs.appendChild(wrap);
  scrollToBottom();
}

/* ─── Append AI placeholder; returns bubble ─── */
function appendAIPlaceholder() {
  const wrap   = document.createElement('div');
  wrap.className = 'content-wrap';
  wrap.id = 'active-ai-wrap';

  const row    = document.createElement('div');
  row.className = 'msg-row ai';

  const av = document.createElement('div');
  av.className = 'avatar';
  av.innerHTML = avatarSVG();

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = `<div class="typing-dots"><span></span><span></span><span></span></div>`;

  row.appendChild(av);
  row.appendChild(bubble);
  wrap.appendChild(row);
  chatMsgs.appendChild(wrap);
  scrollToBottom();
  return bubble;
}

function formatResponse(text) {
  if (!text) return '';

  return text
    .replace('# Answer', '')
    .replace(/\*\*(.*?)\*\*/g, '$1')

    // 🔥 UNIVERSAL LINK HANDLING
    .replace(
      /([A-Za-z\s]+:\s*)(https?:\/\/\S+)/g,
      '$1<a href="$2" target="_blank" rel="noopener noreferrer" style="color:#4da6ff;">View</a>'
    )

    .trim();
}

function typeText(bubble, html, onDone) {
  const parts = html.split(/(<a.*?>.*?<\/a>)/g); // 🔥 split links safely
  let index = 0;

  bubble.innerHTML = '';

  function tick() {
    if (!isProcessing) return;

    if (index < parts.length) {
      const part = parts[index];

      if (part.startsWith('<a')) {
        // 🔥 insert full link instantly (clickable immediately)
        bubble.innerHTML += part;
      } else {
        // 🔥 type normal text slowly
        let i = 0;

        function typeChunk() {
          if (i < part.length) {
            bubble.innerHTML += part[i++];
            scrollToBottom();
            setTimeout(typeChunk, 10);
          } else {
            index++;
            tick();
          }
        }

        typeChunk();
        return;
      }

      index++;
      setTimeout(tick, 30);
    } else {
      onDone();
    }
  }

  tick();
}
/* ─── Stop response ─── */
function stopResponse() {
  clearTimeout(typeTimer);
  isProcessing = false;

  const wrap = document.getElementById('active-ai-wrap');
  if (wrap) {
    const bubble = wrap.querySelector('.bubble');
    if (bubble) {
      const existing = bubble.textContent.trim();
      if (!existing || bubble.querySelector('.typing-dots')) {
        bubble.innerHTML = '<span class="stopped-msg">Response stopped.</span>';
      } else {
        bubble.textContent += '…';
      }
    }
    wrap.removeAttribute('id');
  }
  updateSendState();
}

/* ─── Main send handler (UPDATED) ─── */
function handleSend() {
  const text = textarea.value.trim();
  if (!text || isProcessing) return;

  activateChat();
  appendUserMessage(text);
  textarea.value = '';
  textarea.style.height = 'auto';

  isProcessing = true;
  updateSendState();

  const bubble = appendAIPlaceholder();

  // 🔥 REPLACED: dummy response → real backend call
  fetch("http://127.0.0.1:8000/query", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      question: text
    })
  })
  .then(res => res.json())
  .then(data => {
    if (!isProcessing) return;

    const reply = formatResponse(data.answer || "No response received");

    typeText(bubble, reply, () => {
      isProcessing = false;
      const wrap = document.getElementById('active-ai-wrap');
      if (wrap) wrap.removeAttribute('id');
      updateSendState();
    });
  })
  .catch(err => {
    console.error(err);

    typeText(bubble, "⚠️ Unable to connect to server", () => {
      isProcessing = false;
      updateSendState();
    });
  });
}

/* ─── Scroll to bottom ─── */
function scrollToBottom() {
  chatScroll.scrollTop = chatScroll.scrollHeight;
}
