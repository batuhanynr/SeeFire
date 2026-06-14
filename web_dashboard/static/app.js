const POLL_MS = 1000;
const SNAPSHOT_POLL_MS = 10000;

const stateDescriptions = {
    OFFLINE: "Robot prosesi veya M7 veritabani henuz veri uretmiyor.",
    INIT: "Sistem baslatiliyor veya ilk olay bekleniyor.",
    NAVIGATE: "Robot rota uzerinde ilerliyor.",
    VERIFY: "Risk yuksek; karar motoru dogrulama modunda.",
    ALARM: "Yangin alarm durumu aktif.",
    STOP: "Robot durdu veya gorev sonlandi.",
};

const stateClasses = {
    OFFLINE: "state-offline",
    INIT: "state-init",
    NAVIGATE: "state-navigate",
    VERIFY: "state-verify",
    ALARM: "state-alarm",
    STOP: "state-stop",
};

let configLoaded = false;
let cameraStarted = false;
let manualEnabled = false;
const activeManualKeys = new Set();
let lastManualCommand = "STOP";
let lastSnapshotSignature = "";
let manualHeartbeatTimer = null;

function $(id) {
    return document.getElementById(id);
}

function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
}

function numberOrZero(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n : 0;
}

function setText(id, value) {
    const el = $(id);
    if (el) el.textContent = value;
}

function setBadge(id, online, label) {
    const el = $(id);
    if (!el) return;
    el.classList.toggle("badge-online", online);
    el.classList.toggle("badge-offline", !online);
    const text = el.querySelector(".status-text");
    if (text) text.textContent = label;
}

function setMiniBar(id, value, maxValue) {
    const el = $(id);
    if (!el) return;
    const pct = maxValue > 0 ? clamp((numberOrZero(value) / maxValue) * 100, 0, 100) : 0;
    el.style.width = `${pct}%`;
}

function formatFixed(value, digits = 1) {
    const n = Number(value);
    return Number.isFinite(n) ? n.toFixed(digits) : "--";
}

function parseSensorData(raw) {
    if (!raw) return {};
    if (typeof raw === "object") return raw;
    try {
        return JSON.parse(raw);
    } catch {
        return {};
    }
}

function formatTimestamp(value) {
    if (!value) return { time: "--", date: "" };
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return { time: value, date: "" };
    }
    return {
        time: date.toLocaleTimeString("tr-TR", { hour12: false }),
        date: date.toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit" }),
    };
}

function formatSnapshotTime(snapshot) {
    if (snapshot.timestamp) return formatTimestamp(snapshot.timestamp);
    if (snapshot.mtime) return formatTimestamp(new Date(snapshot.mtime * 1000).toISOString());
    return { time: "--", date: "" };
}

function formatBytes(bytes) {
    const n = Number(bytes);
    if (!Number.isFinite(n)) return "--";
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function formatEvent(rawType) {
    const type = String(rawType || "").trim();
    const upper = type.toUpperCase();
    const snapshot = type.match(/^SNAPSHOT_(.+)$/i);
    const labels = {
        on: "Ön tarama",
        sag: "Sağ tarama",
        sol: "Sol tarama",
    };

    if (snapshot) {
        const key = snapshot[1];
        const segmentMatch = key.match(/^seg(\d+)-(.+)$/i);
        const obstacleMatch = key.match(/^obstacle-seg(\d+)-(\d+)cm$/i);

        if (segmentMatch) {
            const direction = labels[segmentMatch[2]] || segmentMatch[2];
            return {
                badge: "Snapshot",
                className: "scan",
                title: `Segment ${segmentMatch[1]} - ${direction}`,
                detail: type,
            };
        }

        if (obstacleMatch) {
            return {
                badge: "Engel",
                className: "warning",
                title: `Engel görüntüsü - Segment ${obstacleMatch[1]}`,
                detail: `${obstacleMatch[2]} cm mesafede snapshot`,
            };
        }

        return {
            badge: "Snapshot",
            className: "scan",
            title: key.replaceAll("_", " "),
            detail: type,
        };
    }

    if (upper.includes("ALARM")) {
        return { badge: "Alarm", className: "alarm", title: "Yangın alarmı", detail: type };
    }
    if (upper.includes("VERIFY")) {
        return { badge: "Kontrol", className: "warning", title: "Risk doğrulama", detail: type };
    }
    if (upper.includes("STOP")) {
        return { badge: "Durdu", className: "stop", title: "Sistem durdu", detail: type };
    }

    return { badge: "Olay", className: "navigate", title: type || "Bilinmeyen olay", detail: "" };
}

function updateClock() {
    setText("clock", new Date().toLocaleTimeString("tr-TR", { hour12: false }));
}

function updateCamera(status) {
    if (status.manual_mock) {
        const img = $("camera-feed");
        const placeholder = $("camera-placeholder");
        const badge = $("camera-status");
        if (img) img.removeAttribute("src");
        placeholder?.classList.remove("hidden");
        placeholder?.classList.add("mock-camera");
        if (badge) badge.textContent = "Mock kamera";
        cameraStarted = true;
        return;
    }

    if (cameraStarted) return;

    const host = window.location.hostname || "localhost";
    const protocol = window.location.protocol || "http:";
    const streamPort = status.stream_port || 8080;
    const streamUrl = `${protocol}//${host}:${streamPort}/stream`;
    const img = $("camera-feed");
    const placeholder = $("camera-placeholder");
    const badge = $("camera-status");

    img.src = streamUrl;
    img.onload = () => {
        placeholder?.classList.add("hidden");
        if (badge) badge.textContent = "Canli";
    };
    img.onerror = () => {
        placeholder?.classList.remove("hidden");
        if (badge) badge.textContent = "Stream yok";
    };
    cameraStarted = true;
}

function updateState(status) {
    const state = status.fsm_state || "OFFLINE";
    const stateEl = $("fsm-state");
    if (stateEl) {
        stateEl.className = `fsm-state ${stateClasses[state] || "state-offline"}`;
        const name = stateEl.querySelector(".state-name");
        if (name) name.textContent = state;
    }
    setText("fsm-desc", stateDescriptions[state] || stateDescriptions.OFFLINE);
}

function updateFusion(status) {
    const score = clamp(numberOrZero(status.fusion_score), 0, 1);
    setText("fusion-value", score.toFixed(2));
    const fill = $("fusion-fill");
    if (fill) fill.style.width = `${score * 100}%`;

    const threshold = status.config?.thresholds?.fusion_alarm ?? 0.6;
    const marker = $("fusion-thresh-marker");
    if (marker) marker.style.left = `${clamp(threshold * 100, 0, 100)}%`;
    setText("thresh-val", Number(threshold).toFixed(2));
}

function updateSensors(status) {
    const s = status.sensors || {};
    const temp = numberOrZero(s.temperature);
    const smoke = numberOrZero(s.smoke);
    const fire = numberOrZero(s.fire_confidence);
    const distance = numberOrZero(s.distance);

    setText("val-temp", temp ? temp.toFixed(1) : "--");
    setText("val-smoke", smoke ? String(Math.round(smoke)) : "--");
    setText("val-fire", fire ? String(Math.round(fire * 100)) : "--");
    setText("val-distance", distance ? distance.toFixed(1) : "--");
    setText("val-front", s.front_cm !== undefined && s.front_cm !== null ? Number(s.front_cm).toFixed(1) : "--");
    setText(
        "val-sides",
        s.left_cm !== undefined && s.left_cm !== null && s.right_cm !== undefined && s.right_cm !== null
            ? `${Number(s.left_cm).toFixed(0)} / ${Number(s.right_cm).toFixed(0)}`
            : "--",
    );
    setText("val-battery", s.battery_v !== undefined && s.battery_v !== null ? Number(s.battery_v).toFixed(2) : "--");
    setText(
        "val-motor",
        s.left_pwm !== undefined && s.right_pwm !== undefined
            ? `${Number(s.left_pwm).toFixed(0)} / ${Number(s.right_pwm).toFixed(0)}`
            : "--",
    );
    setText("manual-command", s.command || "STOP");

    setMiniBar("bar-temp", temp, 80);
    setMiniBar("bar-smoke", smoke, 4095);
    setMiniBar("bar-fire", fire, 1);

    const overlay = $("vision-overlay");
    const fireConfOverlay = $("fire-conf-overlay");
    const fireSideOverlay = $("fire-side-overlay");
    if (fire > 0.01 || s.fire_side) {
        overlay?.classList.remove("hidden");
        if (fireConfOverlay) fireConfOverlay.textContent = `${Math.round(fire * 100)}%`;
        if (fireSideOverlay) fireSideOverlay.textContent = s.fire_side || "FIRE";
    } else {
        overlay?.classList.add("hidden");
    }
}

function syncManualUi(status) {
    manualEnabled = Boolean(status.manual_mock || status.manual_live);
    if (status.manual_live) {
        setText("manual-mode", "CANLI GPIO - W/A/S/D + SPACE + P");
    } else {
        setText("manual-mode", manualEnabled ? "W/A/S/D + SPACE + P" : "Canlı veri");
    }
}

function updateEvents(events) {
    const body = $("events-body");
    if (!body) return;

    setText("event-count", `${events.length} olay`);

    if (!events.length) {
        body.innerHTML = '<tr class="empty-row"><td colspan="6">Henuz olay kaydedilmedi</td></tr>';
        return;
    }

    body.innerHTML = events.map((event) => {
        const sensor = parseSensorData(event.sensor_data);
        const when = formatTimestamp(event.timestamp);
        const displayEvent = formatEvent(event.event_type);
        const score = Number(event.fusion_score || 0);
        const smoke = sensor.smoke ?? "--";
        const temp = sensor.temp !== undefined ? Number(sensor.temp).toFixed(1) : "--";
        const fire = sensor.fire_conf !== undefined ? `${Math.round(Number(sensor.fire_conf) * 100)}%` : "--";
        return `
            <tr>
                <td class="col-time">
                    <span class="event-time mono">${when.time}</span>
                    <span class="event-date">${when.date}</span>
                </td>
                <td class="col-event">
                    <span class="event-type ${displayEvent.className}">${displayEvent.badge}</span>
                    <div class="event-main">${displayEvent.title}</div>
                    <div class="event-detail">${displayEvent.detail}</div>
                </td>
                <td class="col-num mono">${score.toFixed(2)}</td>
                <td class="col-num mono">${smoke}</td>
                <td class="col-num mono">${temp}</td>
                <td class="col-num mono">${fire}</td>
            </tr>
        `;
    }).join("");
}

function updateSnapshots(snapshots) {
    const grid = $("snapshot-grid");
    if (!grid) return;

    setText("snapshot-count", `${snapshots.length} görüntü`);

    if (!snapshots.length) {
        grid.innerHTML = '<div class="snapshot-empty">Henüz snapshot yok</div>';
        return;
    }

    grid.innerHTML = snapshots.map((snapshot) => {
        const when = formatSnapshotTime(snapshot);
        const displayEvent = formatEvent(snapshot.event_type);
        const sensor = snapshot.sensor_data || {};
        const score = snapshot.fusion_score === null || snapshot.fusion_score === undefined
            ? "--"
            : Number(snapshot.fusion_score).toFixed(2);
        const fire = sensor.fire_conf === undefined ? "--" : `${Math.round(Number(sensor.fire_conf) * 100)}%`;
        return `
            <article class="snapshot-card">
                <a class="snapshot-thumb" href="${snapshot.url}" target="_blank" rel="noopener">
                    <img src="${snapshot.url}" alt="${displayEvent.title}" loading="lazy">
                    <span class="snapshot-open">Yeni sekmede aç</span>
                </a>
                <div class="snapshot-body">
                    <span class="event-type ${displayEvent.className}">${displayEvent.badge}</span>
                    <h3>${displayEvent.title}</h3>
                    <p>${when.date} ${when.time} · #${snapshot.event_id ?? "dosya"}</p>
                    <div class="snapshot-meta">
                        <span>Füzyon <b>${score}</b></span>
                        <span>Ateş <b>${fire}</b></span>
                        <span>${formatBytes(snapshot.size_bytes)}</span>
                    </div>
                </div>
            </article>
        `;
    }).join("");
}

async function refreshSnapshots(force = false) {
    try {
        const snapshotData = await fetchJson("/api/snapshots?limit=80");
        const snapshots = Array.isArray(snapshotData.snapshots) ? snapshotData.snapshots : [];
        const signature = snapshots
            .map((snapshot) => `${snapshot.filename || snapshot.url}:${snapshot.mtime || snapshot.size_bytes || ""}`)
            .join("|");
        if (!force && signature === lastSnapshotSignature) return;
        lastSnapshotSignature = signature;
        updateSnapshots(snapshots);
    } catch {
        setText("snapshot-count", "snapshot okunamadi");
    }
}

function renderConfig(config) {
    const grid = $("config-grid");
    if (!grid) return;

    const thresholds = config.thresholds || {};
    const battery = config.battery || {};
    const weights = config.fusion_weights || {};
    const nav = config.navigation || {};

    const items = [
        ["Duman esigi", thresholds.smoke, "ADC"],
        ["IR sicaklik", thresholds.ir_temp, "C"],
        ["Vision conf", thresholds.vision_conf, ""],
        ["Fusion alarm", thresholds.fusion_alarm, ""],
        ["Fusion clear", thresholds.fusion_clear, ""],
        ["Engel mesafe", thresholds.obstacle_cm, "cm"],
        ["Batarya dusuk", battery.low_v, "V"],
        ["Batarya kritik", battery.critical_v, "V"],
        ["Agirlik vision", weights.vision, ""],
        ["Agirlik smoke", weights.smoke, ""],
        ["Agirlik IR", weights.ir, ""],
        ["Surus hizi", nav.drive_speed, "PWM"],
    ];

    grid.innerHTML = items.map(([label, value, unit]) => `
        <div class="config-item">
            <span>${label}</span>
            <strong class="mono">${value ?? "--"} ${unit}</strong>
        </div>
    `).join("");
}

async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`${url}: ${response.status}`);
    return response.json();
}

async function refreshConfigOnce() {
    if (configLoaded) return;
    const config = await fetchJson("/api/config");
    renderConfig(config);
    configLoaded = true;
}

async function refresh() {
    try {
        const [status, events] = await Promise.all([
            fetchJson("/api/status"),
            fetchJson("/api/events?limit=30"),
        ]);

        updateCamera(status);
        syncManualUi(status);
        setBadge("robot-badge", Boolean(status.robot_running), status.robot_running ? "Robot ON" : "Robot OFF");
        setBadge("connection-badge", Boolean(status.connected), status.connected ? "DB LIVE" : "DB WAIT");
        updateState(status);
        updateFusion(status);
        updateSensors(status);
        updateEvents(Array.isArray(events) ? events : []);
        setText("last-update-footer", `Son guncelleme: ${new Date().toLocaleTimeString("tr-TR", { hour12: false })}`);
        await refreshConfigOnce();
    } catch (err) {
        setBadge("connection-badge", false, "API OFF");
        setText("fsm-desc", `Panel API okunamadi: ${err.message}`);
    }
}

function commandFromKeys() {
    const forward = activeManualKeys.has("w");
    const backward = activeManualKeys.has("s");
    const left = activeManualKeys.has("a");
    const right = activeManualKeys.has("d");
    if (forward && left) return "FORWARD_LEFT";
    if (forward && right) return "FORWARD_RIGHT";
    if (forward) return "FORWARD";
    if (backward) return "BACKWARD";
    if (left && !right) return "LEFT";
    if (right && !left) return "RIGHT";
    return "STOP";
}

async function sendManualCommand(command, force = false) {
    if (!manualEnabled && command !== "STOP") return;
    if (!force && command === lastManualCommand) return;
    lastManualCommand = command;
    setText("manual-command", command);
    try {
        await fetch("/api/manual/command", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ command }),
        });
    } catch (err) {
        setText("manual-command", "LINK ERR");
    }
}

function handleManualKeyDown(event) {
    const key = event.key.toLowerCase();
    if (!["w", "a", "s", "d", " ", "p"].includes(key)) return;
    if (!manualEnabled) return;
    event.preventDefault();
    if (key === "p") {
        captureManualSnapshot();
        return;
    }
    if (key === " ") {
        activeManualKeys.clear();
        sendManualCommand("STOP");
        return;
    }
    activeManualKeys.add(key);
    sendManualCommand(commandFromKeys());
}

function handleManualKeyUp(event) {
    const key = event.key.toLowerCase();
    if (!["w", "a", "s", "d"].includes(key)) return;
    if (!manualEnabled) return;
    event.preventDefault();
    activeManualKeys.delete(key);
    sendManualCommand(commandFromKeys());
}

function startManualHeartbeat() {
    if (manualHeartbeatTimer) return;
    manualHeartbeatTimer = setInterval(() => {
        if (!manualEnabled || activeManualKeys.size === 0) return;
        sendManualCommand(commandFromKeys(), true);
    }, 150);
}

function stopManualInput() {
    if (!manualEnabled) return;
    activeManualKeys.clear();
    sendManualCommand("STOP", true);
}

async function captureManualSnapshot() {
    if (!manualEnabled) return;
    setText("snapshot-count", "snapshot alınıyor...");
    try {
        const response = await fetch("/api/manual/snapshot", { method: "POST" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const result = await response.json();
        setText("snapshot-count", result.message || (result.ok ? "snapshot alındı" : "snapshot başarısız"));
        await refresh();
        await refreshSnapshots(true);
    } catch (err) {
        setText("snapshot-count", `snapshot hata: ${err.message}`);
    }
}

async function clearSnapshots() {
    if (!confirm("Tüm snapshot görüntü dosyaları silinsin mi? Olay günlüğü DB kayıtları korunacak.")) {
        return;
    }
    const button = $("clear-snapshots");
    if (button) {
        button.disabled = true;
        button.textContent = "Temizleniyor...";
    }
    try {
        const response = await fetch("/api/snapshots/clear", { method: "POST" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const result = await response.json();
        setText("snapshot-count", `${result.deleted || 0} silindi`);
        await refreshSnapshots(true);
    } catch (err) {
        alert(`Snapshot temizleme başarısız: ${err.message}`);
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = "Görüntüleri Temizle";
        }
    }
}

updateClock();
window.addEventListener("keydown", handleManualKeyDown);
window.addEventListener("keyup", handleManualKeyUp);
window.addEventListener("blur", stopManualInput);
window.addEventListener("pagehide", stopManualInput);
document.addEventListener("visibilitychange", () => {
    if (document.hidden) stopManualInput();
});
$("clear-snapshots")?.addEventListener("click", clearSnapshots);
setInterval(updateClock, 1000);
startManualHeartbeat();
refresh();
refreshSnapshots(true);
setInterval(refresh, POLL_MS);
setInterval(refreshSnapshots, SNAPSHOT_POLL_MS);
