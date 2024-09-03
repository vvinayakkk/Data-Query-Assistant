document.addEventListener("DOMContentLoaded", function () {
    const chatbox = document.getElementById("chatbox");
    const userInput = document.getElementById("userInput");
    const sendButton = document.getElementById("sendButton");

    sendButton.addEventListener("click", function () {
        const userMessage = userInput.value.trim();
        if (userMessage) {
            appendMessage("user", userMessage);
            sendMessage(userMessage);
            userInput.value = "";
        }
    });

    userInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
            sendButton.click();
        }
    });

    function appendMessage(sender, text) {
        const messageDiv = document.createElement("div");
        messageDiv.className = "message " + sender;

        const textDiv = document.createElement("div");
        textDiv.className = "text";

        // Check if text is an object (which means it's likely a JSON response)
        if (typeof text === "object") {
            textDiv.textContent = JSON.stringify(text, null, 2); // Pretty-print the JSON object
        } else {
            textDiv.textContent = text;
        }

        messageDiv.appendChild(textDiv);
        chatbox.appendChild(messageDiv);
        chatbox.scrollTop = chatbox.scrollHeight;
    }

    function sendMessage(message) {
        fetch("/get_response/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCSRFToken(),
            },
            body: JSON.stringify({
                message: message,
            }),
        })
            .then((response) => response.json())
            .then((data) => {
                if (data.response) {
                    if (Array.isArray(data.response)) {
                        // Handle case where response is an array of objects
                        data.response.forEach((item) => {
                            appendMessage("bot", item);
                        });
                    } else {
                        appendMessage("bot", data.response);
                    }
                } else if (data.error) {
                    appendMessage("bot", "Error: " + data.error);
                }
            })
            .catch((error) => {
                appendMessage("bot", "Error: " + error.message);
            });
    }

    function getCSRFToken() {
        let cookieValue = null;
        if (document.cookie && document.cookie !== "") {
            const cookies = document.cookie.split(";");
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, 10) === "csrftoken=") {
                    cookieValue = decodeURIComponent(cookie.substring(10));
                    break;
                }
            }
        }
        return cookieValue;
    }
});
