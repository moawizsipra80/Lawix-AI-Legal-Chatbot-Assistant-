let findbutton = document.getElementById("chat-form");
findbutton.addEventListener("submit",
    async function (event) {
        event.preventDefault();
        let input = document.getElementById("user-input").value;
        console.log(input);
        if (input == "") {
            return alert("Type Something");
        }
        let messageArea = document.getElementById("message-area");
        let welcomecard = document.querySelector(".welcome-card");
        if (welcomecard) {
            welcomecard.remove();
        }
        let newBubble = document.createElement("div");
        newBubble.classList.add("message", "user");
        newBubble.innerText = input;
        messageArea.appendChild(newBubble);
        document.getElementById("user-input").value = "";
        messageArea.scrollTo({
            top: messageArea.scrollHeight,
            behavior: "smooth"
        })
        try {
            let response = await fetch("/chat?query=" + encodeURIComponent(input));
            let data = await response.json();
            let botbubble = document.createElement("div");
            botbubble.classList.add("message", "bot");
            botbubble.innerText = data.answer;
            messageArea.appendChild(botbubble);
            messageArea.scrollTo({
                top: messageArea.scrollHeight,
                behavior: "smooth"
            })
        }
        catch (error) {
            console.log(error);
            alert("Something went wrong");
        }
    })
