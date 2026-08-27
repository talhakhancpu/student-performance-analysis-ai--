console.log("JavaScript is working!");

const input = document.getElementById("user-input");
const button = document.getElementById("send-button");
const chatBox = document.getElementById("chat-box");


button.addEventListener("click", async function () {

    const message = input.value.trim();

    if (message === "") {
        return;
    }


    const userMessage = document.createElement("div");

    userMessage.classList.add("user-message");

    userMessage.textContent = message;

    chatBox.appendChild(userMessage);

    input.value = "";


    const csrfToken = document.querySelector(
    "[name=csrfmiddlewaretoken]"
).value;


const response = await fetch("/chat/", {

    method: "POST",

    headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken
    },

    body: JSON.stringify({
        message: message
    })

});


    const data = await response.json();


    const botMessage = document.createElement("div");

    botMessage.classList.add("bot-message");

    botMessage.textContent = data.response;

    chatBox.appendChild(botMessage);

});