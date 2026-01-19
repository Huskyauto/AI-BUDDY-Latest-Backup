document.addEventListener('DOMContentLoaded', function() {
    const chatMessages = document.getElementById('chat-messages');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-message');
    const emotionSelect = document.getElementById('emotion-select');
    const customDropdown = document.querySelector('.custom-dropdown');
    const selectedEmotion = document.getElementById('selected-emotion');
    const emotionOptions = document.getElementById('emotion-options');
    const micButton = document.getElementById('mic-button');

    // Speech Recognition Initialization
    let isRecording = false;
    let recognition = null;

    // Initialize speech recognition with cross-browser support
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        recognition = new (window.webkitSpeechRecognition || window.SpeechRecognition)();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onstart = function() {
            isRecording = true;
            micButton.classList.add('recording');
            messageInput.placeholder = 'Listening...';
        };

        recognition.onend = function() {
            isRecording = false;
            micButton.classList.remove('recording');
            messageInput.placeholder = 'Type your message...';
        };

        recognition.onresult = function(event) {
            const transcript = event.results[0][0].transcript;
            messageInput.value = transcript;
            messageInput.focus();
        };

        recognition.onerror = function(event) {
            isRecording = false;
            micButton.classList.remove('recording');
            messageInput.placeholder = 'Type your message...';
            if (event.error === 'not-allowed') {
                appendMessage('System', 'Please enable microphone access to use voice input.');
            }
        };
    }

    // Microphone button click handler
    if (micButton) {
        micButton.addEventListener('click', function() {
            if (!recognition) {
                appendMessage('System', 'Speech recognition is not supported in your browser.');
                return;
            }

            if (isRecording) {
                recognition.stop();
            } else {
                recognition.start();
            }
        });
    }

    // Load chat history function definition
    function loadChatHistory() {
        fetch('/history')
            .then(response => response.json())
            .then(history => {
                chatMessages.innerHTML = '';
                history.reverse().forEach((chat, index) => {
                    setTimeout(() => {
                        appendMessage('You', chat.message);
                        setTimeout(() => {
                            appendMessage('AI-BUDDY', chat.response);
                        }, 300);
                    }, index * 600);
                });
                // Only scroll chat area after loading history
                scrollChatToBottom();
            })
            .catch(error => {
                console.error('Error loading chat history:', error);
                appendMessage('System', 'Error loading chat history. Please refresh the page.');
            });
    }

    // Call loadChatHistory when page loads
    loadChatHistory();

    // Custom dropdown handling
    selectedEmotion.addEventListener('click', function(e) {
        e.stopPropagation();
        customDropdown.classList.toggle('open');
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (!customDropdown.contains(e.target)) {
            customDropdown.classList.remove('open');
        }
    });

    // Handle emotion selection
    const emotionOptionElements = document.querySelectorAll('.emotion-option');
    emotionOptionElements.forEach(option => {
        option.addEventListener('click', function(e) {
            e.stopPropagation();
            const value = this.dataset.value;
            const emoji = this.querySelector('.emoji').textContent;
            const text = this.querySelector('.text').textContent;

            emotionSelect.value = value;
            selectedEmotion.querySelector('.emoji').textContent = emoji;
            selectedEmotion.querySelector('.text').textContent = text;

            emotionOptionElements.forEach(opt => opt.classList.remove('selected'));
            this.classList.add('selected');

            customDropdown.classList.remove('open');
        });
    });

    // Send message handlers
    sendButton.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    function sendMessage() {
        const message = messageInput.value.trim();
        const emotion = emotionSelect.value;

        if (!message) return;

        sendButton.classList.add('sending');
        sendButton.disabled = true;
        messageInput.disabled = true;

        appendMessage('You', message);
        messageInput.value = '';

        fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                emotion: emotion
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success' && data.response) {
                setTimeout(() => {
                    appendMessage('AI-BUDDY', data.response);
                }, 500);
            } else {
                appendMessage('System', data.message || 'Sorry, there was an error processing your message.');
            }
            scrollChatToBottom();
        })
        .catch(error => {
            console.error('Error:', error);
            appendMessage('System', 'Sorry, there was an error sending your message.');
            scrollChatToBottom();
        })
        .finally(() => {
            sendButton.classList.remove('sending');
            sendButton.disabled = false;
            messageInput.disabled = false;
            messageInput.focus();
        });
    }

    function appendMessage(sender, message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender === 'You' ? 'user-message' : sender === 'System' ? 'system-message' : 'ai-message'}`;
        messageDiv.innerHTML = `
            <div class="message-content">
                <strong>${sender}:</strong> ${message}
            </div>
        `;
        chatMessages.appendChild(messageDiv);
        scrollChatToBottom();
    }

    // Only scroll the chat messages container
    function scrollChatToBottom() {
        if (chatMessages) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }
});