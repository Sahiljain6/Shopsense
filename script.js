const messagesEl = document.querySelector('#messages');
const chatForm = document.querySelector('#chatForm');
const userInput = document.querySelector('#userInput');
const sendButton = document.querySelector('#sendButton');
const apiKeyInput = document.querySelector('#apiKey');
const endpointInput = document.querySelector('#endpoint');
const modelInput = document.querySelector('#model');
const saveSettingsButton = document.querySelector('#saveSettings');

const systemPrompt = `You are ShopSense, a friendly shopping assistant. Give simple, practical product advice. Ask one short clarifying question only when needed. Never claim live stock or live prices unless the user provides them.`;
const history = [];

function loadSettings() {
  apiKeyInput.value = localStorage.getItem('shopsense_api_key') || '';
  endpointInput.value = localStorage.getItem('shopsense_endpoint') || endpointInput.value;
  modelInput.value = localStorage.getItem('shopsense_model') || modelInput.value;
}

function saveSettings() {
  localStorage.setItem('shopsense_api_key', apiKeyInput.value.trim());
  localStorage.setItem('shopsense_endpoint', endpointInput.value.trim());
  localStorage.setItem('shopsense_model', modelInput.value.trim());
  addMessage('bot', 'Settings saved in this browser. You can now send a message.');
}

function addMessage(role, text) {
  const bubble = document.createElement('div');
  bubble.className = `message ${role}`;
  bubble.textContent = text;
  messagesEl.appendChild(bubble);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function offlineReply(message) {
  return `Demo answer for: "${message}"

To shop smarter:
1. Set your max budget, including shipping and accessories.
2. Pick the 2-3 features that matter most.
3. Compare recent reviews, warranty, return policy, and seller reputation.
4. Avoid paying extra for features you will not use.

Add an API key or use your own proxy endpoint to enable live AI replies.`;
}

async function askBot(message) {
  const apiKey = apiKeyInput.value.trim();
  const endpoint = endpointInput.value.trim();
  const model = modelInput.value.trim() || 'gpt-4o-mini';

  if (!apiKey) return offlineReply(message);

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model,
      messages: [
        { role: 'system', content: systemPrompt },
        ...history,
        { role: 'user', content: message },
      ],
      temperature: 0.4,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API request failed (${response.status}): ${errorText}`);
  }

  const data = await response.json();
  return data.choices?.[0]?.message?.content?.trim() || 'No answer was returned by the API.';
}

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const message = userInput.value.trim();
  if (!message) return;

  addMessage('user', message);
  history.push({ role: 'user', content: message });
  userInput.value = '';
  sendButton.disabled = true;
  sendButton.textContent = 'Thinking...';

  try {
    const answer = await askBot(message);
    history.push({ role: 'assistant', content: answer });
    addMessage('bot', answer);
  } catch (error) {
    addMessage('bot', error instanceof Error ? error.message : 'Something went wrong.');
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = 'Send';
    userInput.focus();
  }
});

saveSettingsButton.addEventListener('click', saveSettings);
loadSettings();
addMessage('bot', 'Hi! I am ShopSense. Tell me what you want to buy, your budget, and what matters most.');
