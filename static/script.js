//// static/script.js
document.addEventListener('DOMContentLoaded', () => {
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');

    // --- Client-side Session ID (Simple) ---
    // Gets or creates a unique ID for the user's browser session.
    // This ID is sent to the backend to maintain the user's order state.
    let userId = localStorage.getItem('foodChatUserId');
    if (!userId) {
        // Generate a simple unique ID
        userId = 'user_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
        localStorage.setItem('foodChatUserId', userId);
        console.log("New user session ID generated:", userId);
    } else {
        console.log("Using existing user session ID:", userId);
    }


    // --- Function to add a message bubble to the chat box ---
    function addMessage(text, sender) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', `${sender}-message`);

        const bubbleElement = document.createElement('span');
        bubbleElement.classList.add('message-bubble');
        bubbleElement.textContent = text; // Use textContent for security and displaying line breaks

        messageElement.appendChild(bubbleElement);
        chatBox.appendChild(messageElement);

        // Automatically scroll to the latest message
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    // --- Function to send message to backend ---
    async function sendMessageToBackend(message) {
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message, user_id: userId }), // Send message and user ID
            });

            if (!response.ok) {
                // Handle HTTP errors (like 500 Internal Server Error)
                console.error('Backend response was not ok:', response.status, response.statusText);
                // Try to read error response body if available (optional)
                const errorBody = await response.text();
                console.error('Error body:', errorBody);
                addMessage("Sorry, something went wrong on the server. Please try again.", 'bot');
                return null; // Indicate failure
            }

            const data = await response.json();
            console.log("Received from backend:", data); // Debugging backend response

            // Update userId just in case backend assigned a new one (e.g., first request)
            if (data.user_id) {
                 userId = data.user_id;
                 localStorage.setItem('foodChatUserId', userId);
            }

            return data; // Return the JSON data from the backend

        } catch (error) {
            console.error('Error sending message or processing response:', error);
            addMessage("Sorry, I'm having trouble connecting right now. Please check the server.", 'bot');
            return null; // Indicate failure
        }
    }

    // --- Main function to process user input ---
    async function processUserInput() {
        const userMessage = userInput.value.trim();
        if (userMessage === '') {
            return; // Ignore empty messages
        }

        // Display the user's message in the chat box
        addMessage(userMessage, 'user');

        // Clear the input field and disable it while waiting for bot
        userInput.value = '';
        userInput.disabled = true;
        sendButton.disabled = true;
        userInput.placeholder = "Bot is thinking...";


        // Send message to backend and get the response
        const backendResponse = await sendMessageToBackend(userMessage);

        // Re-enable input field (unless conversation is completed)
        if (!(backendResponse && backendResponse.status === "completed")) {
             userInput.disabled = false;
             sendButton.disabled = false;
             userInput.placeholder = "Type your order or question...";
        }


        // Display the bot's response if successful
        if (backendResponse && backendResponse.response) {
             addMessage(backendResponse.response, 'bot');
             // Check status returned by backend to disable input if conversation is completed
             if (backendResponse.status === "completed") {
                  userInput.disabled = true;
                  sendButton.disabled = true;
                  userInput.placeholder = "Conversation ended. Refresh for a new order.";
                  // Optionally clear the user ID or handle session end
                  // localStorage.removeItem('foodChatUserId'); // Uncomment to get a new ID on refresh
             }
        }
         userInput.focus(); // Set focus back to input field after processing (if not disabled)
    }

    // --- Event Listeners for sending messages ---
    sendButton.addEventListener('click', processUserInput);

    userInput.addEventListener('keypress', (event) => {
        // Check if the pressed key is Enter (key code 13)
        if (event.key === 'Enter') {
            event.preventDefault(); // Prevent default form submission behavior
            processUserInput();
        }
    });

    // --- Initial welcome message from the bot when the page loads ---
    // We could fetch this from the backend on load, but for simplicity, hardcode first message
    addMessage("Hello! Welcome to our food ordering chat! 👋 Type 'menu' to see what's cooking!", 'bot');
    userInput.focus(); // Set focus to the input field on load
});