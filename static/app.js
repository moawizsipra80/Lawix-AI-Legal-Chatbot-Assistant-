const chatForm = document.getElementById('chatForm');
const messageInput = document.getElementById('messageInput');
const chatBox = document.getElementById('chatBox');

function appendMessage(text, role) {
  const el = document.createElement('p');
  el.className = `msg ${role}`;
  el.textContent = text;
  chatBox.appendChild(el);
  chatBox.scrollTop = chatBox.scrollHeight;
}

appendMessage('Hi! I am your AI customer chatbot assistant. How can I help?', 'bot');

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) return;

  appendMessage(message, 'user');
  messageInput.value = '';

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    });

    const data = await response.json();
    if (!response.ok) {
      appendMessage(data.error || 'Something went wrong.', 'bot');
      return;
    }

    appendMessage(data.reply, 'bot');
  } catch (_error) {
    appendMessage('Unable to connect to the server. Please try again.', 'bot');
  }
});
