function renderState(data) {
    const leaderboard = data.leaderboard || [];
    const events = data.events || [];

    document.getElementById("device-count").textContent = leaderboard.length;
    document.getElementById("total-score").textContent =
        leaderboard.reduce((sum, d) => sum + (d.score || 0), 0);
    document.getElementById("total-pickups").textContent =
        leaderboard.reduce((sum, d) => sum + (d.pickups || 0), 0);

    const tbody = document.getElementById("leaderboard-body");
    tbody.innerHTML = "";

    leaderboard.forEach((row, idx) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${idx + 1}</td>
            <td>${row.student_id}</td>
            <td>${row.device}</td>
            <td>${row.mode}</td>
            <td>${row.score}</td>
            <td>${row.pickups}</td>
            <td>${row.elapsed_sec}s</td>
            <td>${row.last_event}</td>
        `;
        tbody.appendChild(tr);
    });

    const eventList = document.getElementById("event-list");
    eventList.innerHTML = "";
    events.forEach(ev => {
        const li = document.createElement("li");
        li.textContent = `${ev.time} — ${ev.student_id}/${ev.device} — ${ev.event} — mode=${ev.mode}, score=${ev.score}, pickups=${ev.pickups}`;
        eventList.appendChild(li);
    });
}

async function fetchState() {
    try {
        const res = await fetch("/api/state");
        const data = await res.json();
        renderState(data);
    } catch (err) {
        console.error("fetchState failed:", err);
    }
}

function connectWebSocket() {
    const wsStatus = document.getElementById("ws-status");
    const ws = new WebSocket(`ws://${window.location.host}/ws/live`);

    ws.onopen = () => {
        wsStatus.textContent = "Connected";
    };

    ws.onclose = () => {
        wsStatus.textContent = "Disconnected";
        setTimeout(connectWebSocket, 1000);
    };

    ws.onerror = () => {
        wsStatus.textContent = "Disconnected";
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            renderState(data);
        } catch (err) {
            console.error("Bad websocket payload:", err);
        }
    };
}

document.addEventListener("DOMContentLoaded", () => {
    fetchState();
    connectWebSocket();
});