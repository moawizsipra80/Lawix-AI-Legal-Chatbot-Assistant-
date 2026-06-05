function generateUUID() {
    return 'session_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
}

let activeSessionId = localStorage.getItem("aegis_session_id") || generateUUID();
localStorage.setItem("aegis_session_id", activeSessionId);

const messageArea = document.getElementById("message-area");
const chatForm = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");
const sessionsList = document.getElementById("sessions-list");
const newChatBtn = document.getElementById("new-chat-btn");
const activeChatTitle = document.getElementById("active-chat-title");
const welcomeCardHTML = `
    <div class="welcome-card">
        <i class="fa-solid fa-scale-balanced"></i>
        <h2>How can I help you today?</h2>
        <p>I can assist with questions regarding NDAs, intellectual property, GDPR compliance, and business litigation regulations using semantic vector search.</p>
    </div>
`;


function showWelcomeCard() {
    messageArea.innerHTML = welcomeCardHTML;
}

function appendMessage(text, sender) {
    const welcomeCard = document.querySelector(".welcome-card");
    if (welcomeCard) {
        welcomeCard.remove();
    }
    const bubble = document.createElement("div");
    bubble.classList.add("message", sender);
    bubble.innerText = text;
    messageArea.appendChild(bubble);
    messageArea.scrollTo({
        top: messageArea.scrollHeight,
        behavior: "smooth"
    });
}

function appendSystemMessage(text) {
    const welcomeCard = document.querySelector(".welcome-card");
    if (welcomeCard) {
        welcomeCard.remove();
    }
    const bubble = document.createElement("div");
    bubble.classList.add("message", "system");
    bubble.innerText = text;
    messageArea.appendChild(bubble);
    messageArea.scrollTo({
        top: messageArea.scrollHeight,
        behavior: "smooth"
    });
}

function appendTypingIndicator(statusText) {
    const welcomeCard = document.querySelector(".welcome-card");
    if (welcomeCard) {
        welcomeCard.remove();
    }
    const bubble = document.createElement("div");
    bubble.classList.add("message", "bot", "typing-bubble");
    
    const container = document.createElement("div");
    container.classList.add("typing-container");
    
    const textSpan = document.createElement("span");
    textSpan.classList.add("loading-text");
    textSpan.innerText = statusText;
    
    const indicator = document.createElement("div");
    indicator.classList.add("typing-indicator");
    indicator.innerHTML = "<span></span><span></span><span></span>";
    
    container.appendChild(textSpan);
    container.appendChild(indicator);
    bubble.appendChild(container);
    
    messageArea.appendChild(bubble);
    messageArea.scrollTo({
        top: messageArea.scrollHeight,
        behavior: "smooth"
    });
    return bubble;
}

async function loadHistory(sessionId) {
    try {
        messageArea.innerHTML = "";
        const response = await fetch(`/history?session_id=${encodeURIComponent(sessionId)}`);
        const data = await response.json();
        if (data.history && data.history.length > 0) {
            data.history.forEach(msg => {
                const role = msg.role.toLowerCase() === "user" ? "user" : "bot";
                appendMessage(msg.content, role);
            });
        } else {
            showWelcomeCard();
        }
    } catch (error) {
        console.error("Failed to load chat history:", error);
        showWelcomeCard();
    }
}
async function loadSessionsList() {
    try {
        const response = await fetch("/sessions");
        const data = await response.json();
        sessionsList.innerHTML = "";
        let activeSessionExists = false;
        if (data.sessions && data.sessions.length > 0) {
            activeSessionExists = data.sessions.some(s => s.session_id === activeSessionId);
        }

        const listToRender = [...(data.sessions || [])];
        if (!activeSessionExists) {
            listToRender.unshift({
                session_id: activeSessionId,
                first_message: "New Conversation",
                timestamp: Date.now()
            });
        }

        listToRender.forEach(session => {
            const item = document.createElement("div");
            item.classList.add("session-item");
            if (session.session_id === activeSessionId) {
                item.classList.add("active");
                activeChatTitle.innerText = session.first_message || "New Conversation";
            }

            const icon = document.createElement("i");
            icon.classList.add("fa-regular", "fa-message");

            const title = document.createElement("span");
            title.classList.add("session-title");
            title.innerText = session.first_message || "New Conversation";

            const deleteBtn = document.createElement("button");
            deleteBtn.classList.add("session-delete-btn");
            deleteBtn.innerHTML = '<i class="fa-solid fa-trash-can"></i>';
            deleteBtn.addEventListener("click", async (e) => {
                e.stopPropagation();
                if (confirm("Are you sure you want to delete this chat session?")) {
                    await delete_session(session.session_id);
                }
            });

            item.appendChild(icon);
            item.appendChild(title);
            item.appendChild(deleteBtn);

            item.addEventListener("click", () => {
                activeSessionId = session.session_id;
                localStorage.setItem("aegis_session_id", activeSessionId);

                document.querySelectorAll(".session-item").forEach(el => el.classList.remove("active"));
                item.classList.add("active");

                activeChatTitle.innerText = session.first_message || "New Conversation";
                loadHistory(activeSessionId);
            });

            sessionsList.appendChild(item);
        });
    } catch (error) {
        console.error("Failed to load sessions list:", error);
    }
}

newChatBtn.addEventListener("click", () => {
    activeSessionId = generateUUID();
    localStorage.setItem("aegis_session_id", activeSessionId);
    showWelcomeCard();
    activeChatTitle.innerText = "New Conversation";
    loadSessionsList();
});

chatForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    const query = userInput.value.trim();
    if (query === "") {
        return alert("Type Something");
    }

    appendMessage(query, "user");
    userInput.value = "";
    
   

    const typingBubble = appendTypingIndicator("Searching the document & generating response...");

    try {
        const response = await fetch(`/chat?query=${encodeURIComponent(query)}&session_id=${encodeURIComponent(activeSessionId)}`);
        const data = await response.json();
        
        typingBubble.remove();
        appendMessage(data.answer, "bot");

        loadSessionsList();
    } catch (error) {
        if (typingBubble) typingBubble.remove();
        console.error("Error communicating with chat API:", error);
        appendSystemMessage("Error generating response. Please try again in a moment.");
    }
});

loadSessionsList();
loadHistory(activeSessionId);

async function delete_session(sessionId) {
    try {
        await fetch(`/sessions/${encodeURIComponent(sessionId)}`, {
            method: "DELETE"
        });
        
        // If we deleted the active session, switch to a new chat
        if (sessionId === activeSessionId) {
            activeSessionId = generateUUID();
            localStorage.setItem("aegis_session_id", activeSessionId);
            showWelcomeCard();
            activeChatTitle.innerText = "New Conversation";
        }
        
        loadSessionsList();
        loadHistory(activeSessionId);
    }
    catch (error) {
        console.error("Failed to delete session:", error);
    }
}

const fileinput=document.getElementById("pdf-upload")
fileinput.addEventListener("change",async(event)=>{
    const file=fileinput.files[0];
    if(!file)return;
    
    // Inline progress feedback
    appendSystemMessage(`Uploading "${file.name}"...`);
    const statusBubble = appendSystemMessage("Uploading file to server...");

    const formData=new FormData();
    formData.append("file",file);
    try{
        const response=await fetch("/upload",{
            method:"POST",
            body:formData
        });
        const result=await response.json();
        
        if (result.error) {
            statusBubble.remove();
            appendSystemMessage(`Document upload failed: ${result.error}`);
            fileinput.value = "";
            return;
        }
        
        statusBubble.innerText = "PDF uploaded successfully. Processing document text & generating global summary...";
        
        // Poll status in the background
        const pollInterval = setInterval(async () => {
            try {
                const statusRes = await fetch(`/upload/status/${encodeURIComponent(file.name)}`);
                const statusData = await statusRes.json();
                
                if (statusData.status === "completed") {
                    clearInterval(pollInterval);
                    statusBubble.remove();
                    appendSystemMessage(`Document processing completed. Aegis Legal AI has finished reading "${file.name}" (${statusData.details} segments) and is ready to answer questions.`);
                } else if (statusData.status === "failed") {
                    clearInterval(pollInterval);
                    statusBubble.remove();
                    appendSystemMessage(`Document processing failed: ${statusData.details}`);
                }
            } catch (pollErr) {
                console.error("Polling error:", pollErr);
            }
        }, 1500);
    }
    catch(error){
        statusBubble.remove();
        console.error("Error communicating with upload API:",error);
        appendSystemMessage("Error: Failed to upload PDF.");
    }
    
    fileinput.value = ""; // Clear file selector
})
