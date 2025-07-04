document.addEventListener('DOMContentLoaded', function() {
    const messagesContainer = document.getElementById('messages-container');
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const sendSound = document.getElementById('send-sound');
    const receiveSound = document.getElementById('receive-sound');

    // --- IMPORTANT: Retrieve initial chat/payment status from HTML ---
    // These values should be rendered by your Flask backend in index.html
    // Example: <input type="hidden" id="initialRemainingChats" value="{{ remaining_chats }}">
    // Example: <input type="hidden" id="initialIsActiveSubscription" value="{{ is_active_subscription }}">
    // NEW: Example: <input type="hidden" id="chatApiUrl" value="{{ url_for('chat') }}">
    const initialRemainingChatsElement = document.getElementById('initialRemainingChats');
    const initialIsActiveSubscriptionElement = document.getElementById('initialIsActiveSubscription');
    const chatApiUrlElement = document.getElementById('chatApiUrl'); // NEW: Get the element for chat API URL

    let remainingChats = 0;
    let isActiveSubscription = false;
    const chatApiUrl = chatApiUrlElement ? chatApiUrlElement.value : '/chat'; // NEW: Get the chat API URL, fallback to /chat

    if (initialRemainingChatsElement) {
        remainingChats = parseInt(initialRemainingChatsElement.value);
    } else {
        console.error("Error: HTML element with ID 'initialRemainingChats' not found. Cannot determine initial chat count.");
    }

    if (initialIsActiveSubscriptionElement) {
        // Ensure robust boolean conversion: 'True' or 'False' from Flask
        isActiveSubscription = (initialIsActiveSubscriptionElement.value === 'True');
    } else {
        console.error("Error: HTML element with ID 'initialIsActiveSubscription' not found. Cannot determine initial subscription status.");
    }

    // --- DEBUGGING: Log initial values from HTML ---
    console.log("--- Initial Page Load Status ---");
    console.log("remainingChats from HTML:", remainingChats);
    console.log("isActiveSubscription from HTML:", isActiveSubscription);
    console.log("----------------------------------");


    // Format pre-saved assistant messages
    const existingMessages = messagesContainer.querySelectorAll('.message.left .text');
    existingMessages.forEach(el => {
        el.innerHTML = formatLegalText(el.innerHTML);
    });

    // Scroll to bottom initially
    scrollToBottom();

    // --- NEW LOGIC: Check payment status on page load ---
    // If remaining chats are 0 or less AND the user does NOT have an active subscription, show the popup.
    // This assumes 0 or negative remaining chats means they've hit the free limit.
    if (remainingChats <= 0 && !isActiveSubscription) {
        showPaymentPopup("You have reached your free chat limit. Please complete payment to unlock more chats!");
    }

    // Handle form submission
    chatForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const message = userInput.value.trim();
        if (!message) return;

        addMessage(message, 'user');
        playSound('send');
        userInput.value = '';

        const typingIndicator = createTypingIndicator();
        messagesContainer.appendChild(typingIndicator);
        scrollToBottom();

        try {
            // Use the dynamically retrieved chatApiUrl
            const response = await fetch(chatApiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `message=${encodeURIComponent(message)}`
            });

            if (response.status === 402) {
                // Remove typing indicator
                if (typingIndicator.parentNode) messagesContainer.removeChild(typingIndicator);
                // Show payment popup with the specific error message from the server
                const data = await response.json();
                showPaymentPopup(data.error || "Limit reached. Please pay to continue.");
                return; // Stop further processing
            }

            if (!response.ok) throw new Error('Network response was not ok');

            const html = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newMessages = doc.querySelectorAll('.messages li');

            // Remove typing indicator
            if (typingIndicator.parentNode) messagesContainer.removeChild(typingIndicator);

            if (newMessages.length > 0) {
                const lastMessage = newMessages[newMessages.length - 1];
                if (lastMessage.classList.contains('left')) {
                    const messageContent = lastMessage.querySelector('.text').innerHTML;
                    const formattedContent = formatLegalText(messageContent);

                    const formattedMessage = document.createElement('li');
                    formattedMessage.className = 'message left appeared';
                    formattedMessage.innerHTML = `<div class="text">${formattedContent}</div>`;

                    messagesContainer.appendChild(formattedMessage);
                    playSound('receive');
                    scrollToBottom();
                }
            }
        } catch (error) {
            if (typingIndicator.parentNode) messagesContainer.removeChild(typingIndicator);
            console.error('Error:', error);
            addMessage("Sorry, there was an error processing your request.", 'assistant');
            playSound('receive');
        }
    });

    // Modified showPaymentPopup to accept an optional message
    function showPaymentPopup(message = "Please complete your payment to continue.") {
        const paymentModalElement = document.getElementById('paymentModal');
        if (!paymentModalElement) {
            console.error("Payment modal element not found!");
            return;
        }

        // Update the message in the modal body if a specific message is provided
        const paymentModalMessageElement = document.getElementById('paymentModalMessage');
        if (paymentModalMessageElement) {
            paymentModalMessageElement.innerHTML = `<strong class="text-danger">${message}</strong>`;
        } else {
            console.warn("Element with ID 'paymentModalMessage' not found in modal. Message might not be displayed.");
        }

        // Assuming Bootstrap's JavaScript is correctly loaded for this to work
        const paymentModal = new bootstrap.Modal(paymentModalElement);
        paymentModal.show();
    }

    function addMessage(text, sender) {
        const messageElement = document.createElement('li');
        messageElement.className = `message ${sender === 'user' ? 'right' : 'left'} appeared`;

        // Format AI messages differently
        const content = sender === 'user' ? text : formatLegalText(text);
        messageElement.innerHTML = `<div class="text">${content}</div>`;

        messagesContainer.appendChild(messageElement);
        scrollToBottom();
    }

    function formatLegalText(text) {
        // Headings
        let formattedText = text
            .replace(/^### (.*)$/gm, '<h4>$1</h4>')
            .replace(/^## (.*)$/gm, '<h4>$1</h4>');

        // Bold and italic (inline anywhere)
        formattedText = formattedText
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')  // bold
            .replace(/\*(.*?)\*/g, '<em>$1</em>');             // italic

        // Bullet list items
        formattedText = formattedText.replace(/^\s*-\s(.*)$/gm, '<li>$1</li>');

        // Numbered list items
        formattedText = formattedText.replace(/^\s*\d+\.\s(.*)$/gm, '<li>$1</li>');

        // Wrap list blocks
        formattedText = formattedText.replace(/(<li>.*?<\/li>)+/gs, match => {
            return match.match(/^\s*<li>\d+\./) ? `<ol>${match}</ol>` : `<ul>${match}</ul>`;
        });

        // Markdown-style table support
        formattedText = formattedText.replace(/\|(.+)\|\n\|[-| ]+\|\n((\|.*\|\n?)+)/g, (match, headers, rows) => {
            const thead = headers.trim().split('|').map(h => `<th>${h.trim()}</th>`).join('');
            const tbody = rows.trim().split('\n').map(row => {
                const cells = row.trim().split('|').map(c => `<td>${c.trim()}</td>`).join('');
                return `<tr>${cells}</tr>`;
            }).join('');
            return `<table class="legal-table"><thead><tr>${thead}</tr></thead><tbody>${tbody}</tbody></table>`;
        });

        // Add paragraphs and line breaks
        formattedText = formattedText
            .replace(/\n{2,}/g, '</p><p>') // double line break = new paragraph
            .replace(/\n/g, '<br>');       // single = <br>

        // Wrap in <p> if needed
        if (!formattedText.startsWith('<p>')) {
            formattedText = '<p>' + formattedText + '</p>';
        }

        // Remove empty paragraphs
        formattedText = formattedText.replace(/<p>\s*<\/p>/g, '');

        // Optional: Section divider between major blocks
        formattedText = formattedText.replace(/(<\/h2>|<\/ul>|<\/ol>|<\/table>)\s*(<h2>|$)/g, '$1<div class="section-divider"></div>$2');

        return formattedText;
    }


    function createTypingIndicator() {
        const typingElement = document.createElement('li');
        typingElement.className = 'message left appeared';
        typingElement.innerHTML = `
            <div class="text">
                <div class="typing-indicator">
                    <span class="typing-dot"></span>
                    <span class="typing-dot-space"></span>
                    <span class="typing-dot"></span>
                    <span class="typing-dot-space"></span>
                    <span class="typing-dot"></span>
                </div>
            </div>
        `;
        return typingElement;
    }

    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function playSound(type) {
        try {
            if (type === 'send') {
                sendSound.currentTime = 0; // Rewind to start
                sendSound.play();
            } else if (type === 'receive') {
                receiveSound.currentTime = 0;
                receiveSound.play();
            }
        } catch (e) {
            console.log("Couldn't play sound:", e);
        }
    }

    // Auto-focus input on load
    userInput.focus();
});
