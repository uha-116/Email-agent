/* ─── DOM refs ─── */
const textarea = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const chatArea = document.getElementById('chat-area');
const chatScroll = document.getElementById('chat-scroll');
const chatMsgs = document.getElementById('chat-messages');
const welcome = document.getElementById('welcome');
const waitTooltip = document.getElementById('wait-tooltip');

/* ─── State ─── */
let isProcessing = false;
let tooltipTimer = null;
let chatActivated = false;
let currentStream = null;

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
  const wrap = document.createElement('div');
  wrap.className = 'content-wrap';

  const row = document.createElement('div');
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
  const wrap = document.createElement('div');
  wrap.className = 'content-wrap';
  wrap.id = 'active-ai-wrap';

  const row = document.createElement('div');
  row.className = 'msg-row ai';

  const av = document.createElement('div');
  av.className = 'avatar';
  av.innerHTML = avatarSVG();

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = `
  <span id="status-text">🔍 Understanding your question</span>
`;

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
    // Remove markdown header
    .replace(/^#\s+Answer\s*/i, '')

    // **bold** → <strong>
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')

    // Markdown-style links [text](url)
    .replace(
      /\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer" style="color:#4da6ff;">$1</a>'
    )

    // Bare URLs with optional label prefix  →  clickable "View" link
    .replace(
      /(?<!="|'|")(https?:\/\/\S+)/g,
      '<a href="$1" target="_blank" rel="noopener noreferrer" style="color:#4da6ff;">View</a>'
    )

    // Bullet points: lines starting with - or •
    .replace(/^[\-•]\s+(.+)$/gm, '<div style="padding-left:12px;">• $1</div>')

    // Newlines → <br>
    .replace(/\n/g, '<br>')

    .trim();
}

function typeText(bubble, html, onDone) {
  // Split on ALL HTML tags — tags are inserted instantly, plain text typed char-by-char
  const parts = html.split(/(<[^>]+>)/g).filter(p => p.length > 0);
  let index = 0;

  bubble.innerHTML = '';

  function tick() {
    if (index < parts.length) {
      const part = parts[index];

      if (part.startsWith('<')) {
        // 🔥 Insert HTML tag instantly
        bubble.innerHTML += part;
        scrollToBottom();
        index++;
        setTimeout(tick, 5);
      } else {
        // 🔥 Type plain text character by character
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
    } else {
      // 🔥 FINAL FIX: re-apply full HTML to ensure links render correctly
      bubble.innerHTML = html;
      onDone();
    }
  }

  tick();
}
/* ─── Stop response ─── */
function stopResponse() {

  isProcessing = false;

  if (currentStream) {
    currentStream.close();
    currentStream = null;
  }

  const wrap = document.getElementById('active-ai-wrap');
  if (wrap) {
    const bubble = wrap.querySelector('.bubble');
    if (bubble) {
      const existing = bubble.textContent.trim();
      if (!existing) {
        bubble.innerHTML = '<span class="stopped-msg">Response stopped.</span>';
      } else {
        bubble.textContent += '…';
      }
    }
    wrap.removeAttribute('id');
  }
  updateSendState();
}

function updateStatus(text) {
  const el = document.getElementById('status-text');
  if (!el) return;

  el.innerText = text;

  el.classList.add("shimmer-text");
}



/* ─── Main send handler (UPDATED) ─── */
function handleSend() {
  const text = textarea.value.trim();
  if (!text || isProcessing) return;

  if (currentStream) {
    currentStream.close();
    currentStream = null;
  }

  activateChat();
  appendUserMessage(text);
  textarea.value = '';
  textarea.style.height = 'auto';

  isProcessing = true;
  updateSendState();

  const bubble = appendAIPlaceholder();


  const evtSource = new EventSource(
    `http://127.0.0.1:8000/query-stream?q=${encodeURIComponent(text)}`
  );
  currentStream = evtSource;


  evtSource.onmessage = function (event) {
    const data = event.data.trim();

    console.log("📨 SSE event:", JSON.stringify(data));

    if (data.startsWith("FINAL::")) {

      const rawReply = data.replace("FINAL::", "");
      // 🔥 FIX: parse JSON string properly
      let parsedReply = "";

      try {
        parsedReply = JSON.parse(rawReply);
      } catch (e) {
        console.error("JSON parse failed:", e);
        parsedReply = rawReply;
      }
      const reply = formatResponse(parsedReply);

      console.log("✅ Final reply (raw):", rawReply);
      console.log("✅ Final reply (formatted):", reply);

      // 🔥 STEP 1: fade out status text
      bubble.classList.add("fade-out");

      setTimeout(() => {

        // 🔥 STEP 2: clear bubble completely
        bubble.innerHTML = "";

        // 🔥 STEP 3: remove fade class
        bubble.classList.remove("fade-out");

        // 🔥 STEP 4: start typing clean answer
        if (reply) {
          typeText(bubble, reply, () => {
            isProcessing = false;

            const wrap = document.getElementById('active-ai-wrap');
            if (wrap) wrap.removeAttribute('id');

            updateSendState();
          });
        } else {
          // Fallback if reply is empty
          bubble.textContent = rawReply || "No response received.";
          isProcessing = false;

          const wrap = document.getElementById('active-ai-wrap');
          if (wrap) wrap.removeAttribute('id');

          updateSendState();
        }

      }, 300); // matches CSS transition time

      evtSource.close();
      currentStream = null;
    } else {
      // 🔥 update SAME status tag text
      updateStatus(data);
    }
  };

  evtSource.onerror = function (err) {
    console.error(err);


    typeText(bubble, "⚠️ Unable to connect to server", () => {
      isProcessing = false;
      updateSendState();
    });

    evtSource.close();
    currentStream = null;
  };

}

/* ─── Scroll to bottom ─── */
function scrollToBottom() {
  chatScroll.scrollTop = chatScroll.scrollHeight;
}
