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
let responseIndex = 0;

/* ─── Default AI responses ─── */
const AI_RESPONSES = [
  `Several strong opportunities have come up this week that match your profile closely. There are 14 new postings across product, data, and operations roles at fast-growing companies. Three of them are especially aligned with your experience — I'd recommend prioritising those applications before the weekend deadline.`,

  `Your application to the Senior Product Manager role at FinTech Corp has moved to the screening stage — expect a calendar invite in the next 48 hours. Two other companies you bookmarked last month have quietly re-opened their hiring pipelines. Keep your inbox handy; interview invites often land without much notice.`,

  `The job market in your target sector saw a 16 % uptick in postings this month compared to last. Remote-friendly roles are leading the surge, particularly in product management, UX research, and data engineering. Your profile received 11 views this week, which signals strong recruiter interest right now.`,

  `Three companies have you on their shortlist this week. A climate-tech startup is especially keen and may reach out by tomorrow afternoon. The role you applied for at DataBridge is still active — their hiring cycle typically runs three to four weeks, so you're right on schedule for a first-round call.`,

  `No urgent blockers in your pipeline today. You have one pending skills assessment due Friday and two interviews lined up early next week. You're in active consideration for six roles simultaneously, which is a healthy position — stay consistent with follow-ups and you're well on track.`,
];

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

/* ─── Typewriter ─── */
function typeText(bubble, text, onDone) {
  let i = 0;
  bubble.textContent = '';
  function tick() {
    if (!isProcessing) return;
    if (i < text.length) {
      bubble.textContent += text[i++];
      scrollToBottom();
      const delay = text[i-1] === '.' ? 55 : text[i-1] === ',' ? 35 : 14 + Math.random() * 9;
      typeTimer = setTimeout(tick, delay);
    } else {
      onDone();
    }
  }
  typeTimer = setTimeout(tick, 180);
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

/* ─── Main send handler ─── */
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

  setTimeout(() => {
    if (!isProcessing) return;
    const reply = AI_RESPONSES[responseIndex % AI_RESPONSES.length];
    responseIndex++;
    typeText(bubble, reply, () => {
      isProcessing = false;
      const wrap = document.getElementById('active-ai-wrap');
      if (wrap) wrap.removeAttribute('id');
      updateSendState();
    });
  }, 850);
}

/* ─── Scroll to bottom ─── */
function scrollToBottom() {
  // Scroll the hidden inner pane (chatScroll) — no bar shown there.
  // body also scrolls if content overflows — but layout prevents that.
  chatScroll.scrollTop = chatScroll.scrollHeight;
}