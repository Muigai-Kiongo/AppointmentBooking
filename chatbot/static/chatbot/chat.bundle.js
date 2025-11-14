/*
  chat.bundle.js
  - Contains widget JS logic. CSS is now inlined in chat_widget.html, so this file only contains JS.
  Place this file in chatbot/static/chatbot/chat.bundle.js and run collectstatic for production.
*/

(function () {
    // ---------------------------
    // Widget JS (no CSS injection here)
    // ---------------------------
    function el(id) { return document.getElementById(id); }
  
    // Helper: if the widget isn't present (e.g., someone included script without markup),
    // create it dynamically to ensure the bundle can be dropped anywhere.
    function ensureWidgetExists() {
      if (el('chat-widget')) return;
      var container = document.createElement('div');
      container.id = 'chat-widget';
      container.className = 'chat-widget';
      container.innerHTML = `
        <div id="chat-header" class="chat-header">
          <span>Health Assistant</span>
          <button id="chat-close" class="chat-close" aria-label="Close chat">✕</button>
        </div>
        <div id="chat-body" class="chat-body" role="log"></div>
        <div id="chat-footer" class="chat-footer">
          <label style="font-size:12px;">
            <input id="chat-consent" type="checkbox" /> I consent to send non-identifying info (not medical advice)
          </label>
          <input id="chat-input" class="chat-input" placeholder="Describe symptoms or 'book appointment'..." aria-label="Chat input" />
          <button id="chat-send" class="chat-send">Send</button>
          <div id="chat-disclaimer" class="chat-disclaimer">This assistant provides general guidance and is not a substitute for professional medical care.</div>
        </div>
      `;
      document.body.appendChild(container);
    }
  
    ensureWidgetExists();
  
    var body = el('chat-body');
    var input = el('chat-input');
    var send = el('chat-send');
    var consent = el('chat-consent');
    var closeBtn = el('chat-close');
  
    function appendMessage(who, text){
      var d = document.createElement('div');
      d.className = 'chat-msg ' + (who === 'user' ? 'chat-user' : 'chat-bot');
      d.innerText = text;
      body.appendChild(d);
      body.scrollTop = body.scrollHeight;
    }
  
    send.addEventListener('click', function () {
      var msg = input.value.trim();
      if (!msg) return;
      if (!consent.checked) {
        alert('Please give consent to continue.');
        return;
      }
      appendMessage('user', msg);
      input.value = '';
      fetch('/chat/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ message: msg, consent: true, patient_id: null })
      }).then(function (r) {
        return r.json();
      }).then(function (data) {
        if (!data) {
          appendMessage('bot', 'No response from server');
          return;
        }
        if (data.error) {
          appendMessage('bot', 'Error: ' + (data.message || data.error));
          return;
        }
        appendMessage('bot', data.reply || 'No reply');
        if (data.actions && data.actions.suggest_booking && data.actions.booking_url) {
          var link = document.createElement('a');
          link.href = data.actions.booking_url;
          link.innerText = 'Book an appointment';
          link.className = 'chat-book-link';
          body.appendChild(link);
        }
      }).catch(function (err) {
        appendMessage('bot', 'Network error');
        console.error(err);
      });
    });
  
    input.addEventListener('keyup', function (e) {
      if (e.key === 'Enter') send.click();
    });
  
    closeBtn.addEventListener('click', function () { document.getElementById('chat-widget').style.display = 'none'; });
  
  })();