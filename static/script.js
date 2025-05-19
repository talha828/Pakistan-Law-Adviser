document.addEventListener('DOMContentLoaded', function() {
    const messagesContainer = document.getElementById('messages-container');
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const sendSound = document.getElementById('send-sound');
    const receiveSound = document.getElementById('receive-sound');

    // Scroll to bottom initially
    scrollToBottom();

    // Handle form submission
    chatForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const message = userInput.value.trim();
        if (!message) return;

        // Add user message immediately with sound
        addMessage(message, 'user');
        playSound('send');
        userInput.value = '';
        
        // Show typing indicator
        const typingIndicator = createTypingIndicator();
        messagesContainer.appendChild(typingIndicator);
        scrollToBottom();
        
        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `message=${encodeURIComponent(message)}`
            });
            
            if (!response.ok) throw new Error('Network response was not ok');
            
            const html = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newMessages = doc.querySelectorAll('.messages li');
            
            // Remove typing indicator
            messagesContainer.removeChild(typingIndicator);
            
            // Add only the new assistant message with sound
            if (newMessages.length > 0) {
                const lastMessage = newMessages[newMessages.length - 1];
                if (lastMessage.classList.contains('left')) {
                    // Format the message content before displaying
                    const messageContent = lastMessage.querySelector('.text').innerHTML;
                    const formattedContent = formatLegalText(messageContent);
                    
                    // Create new message element with formatted content
                    const formattedMessage = document.createElement('li');
                    formattedMessage.className = 'message left appeared';
                    formattedMessage.innerHTML = `<div class="text">${formattedContent}</div>`;
                    
                    messagesContainer.appendChild(formattedMessage);
                    playSound('receive');
                    scrollToBottom();
                }
            }
        } catch (error) {
            // Remove typing indicator on error
            if (typingIndicator.parentNode) {
                messagesContainer.removeChild(typingIndicator);
            }
            console.error('Error:', error);
            addMessage("Sorry, there was an error processing your request.", 'assistant');
            playSound('receive');
        }
    });

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
        // Convert markdown-style formatting to HTML
        let formattedText = text
            // Bold text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            // Italic text
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            // Headings (lines ending with :)
            .replace(/^(.*?:)\n/gm, '<h4>$1</h4>')
            // Bullet points
            .replace(/\n\s*\*\s(.*?)(?=\n\s*\*|$)/g, '<li>$1</li>')
            // Numbered lists
            .replace(/\n\s*\d+\.\s(.*?)(?=\n\s*\d+\.|$)/g, '<li>$1</li>');
        
        // Wrap list items in UL tags
        formattedText = formattedText.replace(/(<li>.*?<\/li>)+/g, function(match) {
            return match.includes('<ul>') ? match : '<ul>' + match + '</ul>';
        });
        
        // Add section dividers between major sections
        formattedText = formattedText.replace(/(<\/h4>|<\/ul>)\s*(<h4>|$)/g, '$1<div class="section-divider"></div>$2');
        
        // Handle paragraphs and line breaks
        formattedText = formattedText
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');
        
        // Ensure proper wrapping
        if (!formattedText.startsWith('<') && !formattedText.startsWith('<p>')) {
            formattedText = '<p>' + formattedText + '</p>';
        }
        
        // Clean up empty paragraphs
        formattedText = formattedText.replace(/<p><\/p>/g, '');
        
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