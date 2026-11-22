"use strict";

const chatBox = document.getElementById("chatBox");
const userInput = document.getElementById("userInput");
const chatForm = document.getElementById("chatForm");
const sendBtn = document.getElementById("sendBtn");
const voiceStatus = document.getElementById("voiceStatus");

function addMessage(message, sender) {
    const messageDiv = document.createElement("div");
    messageDiv.className = "message " + sender;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = message;

    messageDiv.appendChild(bubble);
    chatBox.appendChild(messageDiv);

    chatBox.scrollTop = chatBox.scrollHeight;

    return messageDiv;
}

async function sendMessage(message) {

    if (!message.trim() || sendBtn.disabled) return;

    addMessage(message, "user");

    userInput.value = "";
    sendBtn.disabled = true;

    const typing = addMessage("Typing...", "bot");

    try {

        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message
            })
        });

        const data = await response.json();

        typing.remove();

        if (!response.ok) {
            throw new Error(data.error || "Server error");
        }

        addMessage(
            data.reply || data.response ||
            "Sorry, I couldn't generate a response.",
            "bot"
        );

        if (data.care && window.CareFinder) {

            showCarePanel(data.care);

        }

    } catch (error) {

        typing.remove();

        addMessage(
            "Sorry, I could not connect to the chatbot. Please check the Flask backend.",
            "bot"
        );

        console.error(error);

    } finally {

        sendBtn.disabled = false;
        userInput.focus();

    }
}

function showCarePanel(care) {

    const wrapper = document.getElementById("careResults");

    addMessage(
        "👇 Suitable doctors and hospitals are listed below.",
        "bot"
    );

    CareFinder.mount(wrapper, {
        urgency: care.urgency,
        specializations: care.specializations,
        condition: care.condition
    });

    wrapper.scrollIntoView({
        block: "start",
        behavior: "smooth"
    });
}

chatForm.addEventListener("submit", function(event) {

    event.preventDefault();

    sendMessage(userInput.value.trim());

});

function askQuestion(question) {
    sendMessage(question);
}

function clearChat() {

    chatBox.innerHTML = "";

    addMessage(
        "Hello! 👋 Welcome back to SmartHealth Assistant. How can I help you today?",
        "bot"
    );

    document.getElementById("careResults").innerHTML = "";
}


// VOICE INPUT

function startVoiceInput() {

    const SpeechRecognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;

    if (!SpeechRecognition) {

        voiceStatus.textContent =
            "Voice recognition is not supported in this browser.";

        return;
    }

    const recognition = new SpeechRecognition();

    recognition.lang = "en-IN";
    recognition.interimResults = false;

    voiceStatus.textContent = "🎤 Listening... Speak now.";

    recognition.onresult = function(event) {

        const spokenText =
            event.results[0][0].transcript;

        userInput.value = spokenText;

        voiceStatus.textContent =
            "Voice input captured successfully!";

    };

    recognition.onerror = function(event) {

        voiceStatus.textContent =
            "Voice error: " + event.error;

    };

    recognition.onend = function() {

        if (voiceStatus.textContent === "🎤 Listening... Speak now.") {
            voiceStatus.textContent = "";
        }

    };

    recognition.start();
}