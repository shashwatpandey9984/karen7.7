let userName = localStorage.getItem("userName");
let voiceEnabled = true; // ✅ Main fix
let isListening = false; // prevent double starts
let streaming = false;
let videoEl = null;
let canvasEl = null;
let overlayCtx = null;
let streamTrackInterval = null;
let frameCanvas = null;
let frameRequestPending = false;
let faceErrorShown = false;
const API_BASE_URL = (window.KAREN_API_BASE_URL || "").replace(/\/+$/, "");

function apiUrl(path) {
  const relativePath = path.replace(/^\/+/, "");
  return API_BASE_URL
    ? new URL(relativePath, `${API_BASE_URL}/`).toString()
    : new URL(relativePath, document.baseURI).toString();
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, character => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[character]);
}

let alarmPlayed = false;

async function checkAlert() {
  try {
    const response = await fetch(apiUrl("/check"));
    if (!response.ok) return;
    const data = await response.json();
    const alarm = document.getElementById("alarmSound");
    if (data.alert && !alarmPlayed) {
      await alarm.play().catch(() => {});
      alarmPlayed = true;
    } else if (!data.alert && alarmPlayed) {
      alarm.pause();
      alarm.currentTime = 0;
      alarmPlayed = false;
    }
  } catch (error) {
    console.error("Error checking alert:", error);
  }
}

if (window.KAREN_API_ENABLED) {
  window.setInterval(checkAlert, 2000);
}

// Load greeting and sync voice button state
window.addEventListener("DOMContentLoaded", function () {
  const voiceBtn = document.getElementById("voiceBtn");
  if (voiceBtn && voiceEnabled) voiceBtn.classList.add("active");

  if (!userName) {
    botRespond("Hello! What should I call you?");
  } else {
    botRespond(`Welcome back, ${escapeHtml(userName)}!`);
  }
});

// Ensure audio gets unlocked when the camera open button is clicked
window.addEventListener("DOMContentLoaded", () => {
  const openBtn =
    document.getElementById("openCamBtn") ||
    document.querySelector('button[onclick="openCameraAndDetect()"]');
  const alarmSound = document.getElementById("alarmSound");
  if (openBtn && alarmSound) {
    openBtn.addEventListener("click", () => {
      alarmSound.play()
        .then(() => {
          alarmSound.pause();
          alarmSound.currentTime = 0;
          console.log("✅ Audio unlocked");
        })
        .catch((err) => console.log(err));
    });
  }
});

// Handle send message
function sendMessage() {
  const input = document.getElementById("userInput");
  const message = input.value.trim();
  if (message === "") return;

  addUserMessage(message);
  input.value = "";
  handleMessage(message);
}

// Show user message
function addUserMessage(text) {
  const chatBox = document.getElementById("chatBox");
  const div = document.createElement("div");
  div.className = "message user";
  div.textContent = text;
  chatBox.appendChild(div);
}

// Show bot message + voice
function botRespond(text) {
  const chatBox = document.getElementById("chatBox");
  const div = document.createElement("div");
  div.className = "message bot";
  div.innerHTML = text;
  chatBox.appendChild(div);

  chatBox.scrollTop = chatBox.scrollHeight;
  botSpeakIfEnabled(text);
}

// Message Logic ✅
async function handleMessage(message) {
  const lowerMsg = message.toLowerCase();

  // Set Name
  if (!userName) {
    userName = message;
    localStorage.setItem("userName", userName);
    botRespond(`Nice to meet you, ${escapeHtml(userName)}!`);
    return;
  }

  // Math checks (added)
  const mathResp = checkMath(message);
  if (mathResp) {
    botRespond(mathResp);
    return;
  }

  // NEWS command (added)
  if (lowerMsg.startsWith("news")) {
    const query = message.slice(4).trim(); // remove "news"
    if (!query) {
      botRespond("Kis topic ya location ka news chahiye?");
      return;
    }
    fetchNews(query);
    return;
  }

  if (lowerMsg.includes("current affairs")) {
    fetchNews(message);
    return;
  }

  // Simple conversational replies (Hindi / English)
  if (lowerMsg === "hello" || lowerMsg === "hi" || lowerMsg === "hey") {
    botRespond("Hello! Karen yaha hai 😎✨ How can I help you?");
    return;
  } else if (lowerMsg.includes("kaise ho")) {
    botRespond("Main mast hoon! Aap kaise ho? 😊");
    return;
  } else if (lowerMsg.includes("good morning")) {
    botRespond("Good Morning! 💚 Have a great day ahead!");
    return;
  } else if (lowerMsg.includes("thank you")) {
    botRespond("You're welcome! 😄 Always here to help!");
    return;
  } else if (lowerMsg.includes("love you")) {
    botRespond("Aww! 🥹 I care for you too 💚");
    return;
  } else if (lowerMsg.includes("karen")) {
    botRespond("Yes buddy? Karen listening! 👂✨");
    return;
  } else if (lowerMsg.includes("bye")) {
    botRespond("Bye Buddy! 💚 Take care!");
    return;
  }

  // Info / Introduction
  if (
    lowerMsg.includes("karen") ||
    lowerMsg.includes("who are you") ||
    lowerMsg.includes("introduce")
  ) {
    const infoHtml = `I am <b>KAREN</b><br>
      </b>`;
    const infoSpeak = "I am KAREN version seven point three. Storage twelve GB. RAM twelve GB. ROM twelve GB.";
    botRespond(infoHtml);
    speak(infoSpeak);
    return;
  }

  // FULL FORM (case-insensitive)
  if (lowerMsg.includes("full form")) {
    const fullHtml = `KAREN FULL FORM IS <b>Knowledgeable Artificial Real-time Enhanced Navigator</b>`;
    const fullSpeak = "K A R E N stands for Knowledgeable Artificial Real-time Enhanced Navigator.";
    botRespond(fullHtml);
    speak(fullSpeak);
    return;
  }

  // Short keyword that asks for version/storage/etc.
  if (
    lowerMsg.includes("version") ||
    lowerMsg.includes("storage") ||
    lowerMsg.includes("ram") ||
    lowerMsg.includes("rom")
  ) {
    const infoSpeak = "I am Karen version seven point three. Storage twelve GB. RAM twelve GB. ROM twelve GB.";
    botRespond("I am KAREN — Version 7.3. Storage: 12GB. RAM: 12GB. ROM: 12GB.");
    speak(infoSpeak);
    return;
  }

  // Wikipedia Search ✅
  if (lowerMsg.startsWith("search on wikipedia") || lowerMsg.startsWith("siw ")) {
    let topic = "";
    if (lowerMsg.startsWith("search on wikipedia")) {
      topic = message.substring("search on wikipedia".length).trim();
    } else {
      topic = message.substring("siw ".length).trim();
    }

    if (!topic) {
      botRespond(`Please write correctly:<br><b>search on wikipedia India</b>`);
      return;
    }
    botRespond("Searching Wikipedia… ⏳");
    return searchWiki(topic);
  }

  // Search hint
  if (lowerMsg.includes("wikipedia")) {
    botRespond(`Use:<br><b>search on wikipedia Taj Mahal</b>`);
    return;
  }

  // Default
  botRespond(generateReply(message));
}

// Math helper (added)
function checkMath(message) {
  const msg = message.toLowerCase();

  // ✅ Table Command
  if (msg.includes("table of") || msg.includes("table")) {
    const numberMatch = msg.match(/\d+/);
    const number = numberMatch ? parseInt(numberMatch[0], 10) : NaN;
    if (!isNaN(number)) {
      let table = `<b>Table of ${number}:</b><br>`;
      for (let i = 1; i <= 10; i++) {
        table += `${number} × ${i} = ${number * i}<br>`;
      }
      return table;
    }
  }

  // ✅ Square Root
  if (msg.includes("under root") || msg.includes("underroot") || msg.includes("√")) {
    const numberMatch = msg.match(/\d+/);
    const number = numberMatch ? parseInt(numberMatch[0], 10) : NaN;
    if (!isNaN(number)) {
      return `√${number} = ${Math.sqrt(number).toFixed(2)}`;
    }
  }

  // ✅ Addition (20 + 10 or add 20 and 10)
  if (msg.includes("add") || msg.includes("+")) {
    const nums = msg.match(/\d+/g);
    if (nums && nums.length >= 2) {
      const result = Number(nums[0]) + Number(nums[1]);
      return `${nums[0]} + ${nums[1]} = ${result}`;
    }
  }

  // ✅ Subtraction (20 - 5 or subtract 20 and 5)
  if (msg.includes("subtract") || (msg.includes("-") && !msg.includes("–"))) {
    const nums = msg.match(/\d+/g);
    if (nums && nums.length >= 2) {
      const result = Number(nums[0]) - Number(nums[1]);
      return `${nums[0]} - ${nums[1]} = ${result}`;
    }
  }

  // ✅ Multiplication (multiply 3 and 7 or 3 × 7)
  if (msg.includes("multiply") || msg.includes(" x ") || msg.includes("*")) {
    const nums = msg.match(/\d+/g);
    if (nums && nums.length >= 2) {
      const result = Number(nums[0]) * Number(nums[1]);
      return `${nums[0]} × ${nums[1]} = ${result}`;
    }
  }

  // ✅ Division (20 ÷ 4 or divide 20 by 4)
  if (msg.includes("divide") || msg.includes("÷") || msg.includes("/")) {
    const nums = msg.match(/\d+/g);
    if (nums && nums.length >= 2 && Number(nums[1]) !== 0) {
      const result = Number(nums[0]) / Number(nums[1]);
      return `${nums[0]} ÷ ${nums[1]} = ${result}`;
    }
  }

  return null;
}

// Basic AI Replies
function generateReply(message) {
  const msg = message.toLowerCase();
  if (msg.includes("hi") || msg.includes("hello")) return `Hello ${escapeHtml(userName)}!`;
  if (msg.includes("who am i")) return `You are ${escapeHtml(userName)}!`;
  return `I'm learning from you, ${escapeHtml(userName)}! 😊`;
}

// ✅ Text To Speech (Hindi + English)
function speak(text) {
  if (!("speechSynthesis" in window) || typeof SpeechSynthesisUtterance === "undefined") {
    return;
  }
  const clean = text.replace(/<\/?[^>]+(>|$)/g, "");
  const speech = new SpeechSynthesisUtterance(clean);
  speech.lang = "hi-IN"; // Hindi first
  speech.pitch = 1;
  speech.rate = 1.05;

  speechSynthesis.cancel();
  setTimeout(() => speechSynthesis.speak(speech), 100);
}

function botSpeakIfEnabled(text) {
  if (voiceEnabled) speak(text);
}

// ✅ Toggle voice (button click)
function toggleVoice() {
  const btn = document.getElementById("voiceBtn");
  if (!("speechSynthesis" in window)) {
    botRespond("Text-to-speech is not supported in this browser.");
    return;
  }
  voiceEnabled = !voiceEnabled;
  if (btn) btn.classList.toggle("active", voiceEnabled);
  if (!voiceEnabled) speechSynthesis.cancel();
}

// ✅ Speech Recognition 🎤
let recognition;
try {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR();
  recognition.lang = "hi-IN"; // Hindi + English Auto
  recognition.continuous = false;
} catch {
  console.log("Speech Recognition Not Supported");
}

// Start listening button
function startListening() {
  if (!recognition) {
    botRespond("Voice Recognition not supported ❌");
    return;
  }

  if (isListening) return; // already listening
  isListening = true;

  const btn = document.getElementById("voiceRecordBtn");
  if (btn) btn.classList.add("listening");

  // set handlers before starting to avoid missing events
  recognition.onresult = function (e) {
    const transcript = e.results && e.results[0] && e.results[0][0] && e.results[0][0].transcript;
    if (transcript) {
      document.getElementById("userInput").value = transcript;
      sendMessage();
    }
  };

  recognition.onend = () => {
    isListening = false;
    if (btn) btn.classList.remove("listening");
  };

  recognition.onerror = (event) => {
    console.error("SpeechRecognition error:", event);
    isListening = false;
    if (btn) btn.classList.remove("listening");
    botRespond("Voice recognition error ❌");
  };

  try {
    recognition.start();
  } catch (err) {
    // start() can throw if called in invalid state
    console.error(err);
    isListening = false;
    if (btn) btn.classList.remove("listening");
  }
}

function createCameraElements() {
  videoEl = document.getElementById("cameraFeed");
  canvasEl = document.getElementById("faceOverlay");
  if (!canvasEl) {
    canvasEl = document.createElement("canvas");
    canvasEl.id = "faceOverlay";
    document.body.appendChild(canvasEl);
  }
  overlayCtx = canvasEl ? canvasEl.getContext("2d") : null;
  frameCanvas = document.createElement("canvas");
}

async function openCameraAndDetect() {
  if (streaming) return;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    botRespond("Camera access requires HTTPS or localhost in a supported browser.");
    return;
  }

  createCameraElements();
  try {
    faceDetectionAvailable = false;
    faceApiCameraStream = await navigator.mediaDevices.getUserMedia({ video: true });
    videoEl.srcObject = faceApiCameraStream;
    videoEl.style.display = "block";
    canvasEl.style.display = "block";
    await videoEl.play();

    streaming = true;
    faceErrorShown = false;
    if (window.KAREN_API_ENABLED) {
      fetch(apiUrl("/set_alert"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alert: false })
      }).catch(err => console.error("Could not reset face alarm:", err));
    }
    await captureAndSendFrame();
    if (!faceErrorShown) {
      streamTrackInterval = setInterval(captureAndSendFrame, 1000);
    }
  } catch (err) {
    console.error("Camera startup error:", err);
    await stopCameraDetection();
    botRespond(`Could not start the camera: ${err.message || err}`);
  }
}

async function stopCameraDetection() {
  streaming = false;
  if (streamTrackInterval) {
    clearInterval(streamTrackInterval);
    streamTrackInterval = null;
  }
  try {
    if (videoEl && videoEl.srcObject) {
      const tracks = videoEl.srcObject.getTracks();
      tracks.forEach(t => t.stop());
      videoEl.srcObject = null;
    }
    if (faceApiCameraStream) {
      faceApiCameraStream.getTracks().forEach(track => track.stop());
      faceApiCameraStream = null;
    }
  } catch (e) {
    console.error("Camera cleanup error:", e);
  }

  if (overlayCtx && canvasEl) {
    overlayCtx.clearRect(0, 0, canvasEl.width || 0, canvasEl.height || 0);
  }
  if (videoEl) videoEl.style.display = "none";
  if (canvasEl) canvasEl.style.display = "none";
  if (faceDetectionAvailable) {
    fetch(apiUrl("/set_alert"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ alert: false })
    }).catch(err => console.error("Could not clear face alarm:", err));
  }
}

let faceDetectionAvailable = false;

async function captureAndSendFrame() {
  if (!streaming || frameRequestPending || !videoEl || videoEl.readyState < 2) return;

  frameRequestPending = true;
  try {
    const scale = Math.min(1, 640 / videoEl.videoWidth, 640 / videoEl.videoHeight);
    frameCanvas.width = Math.round(videoEl.videoWidth * scale);
    frameCanvas.height = Math.round(videoEl.videoHeight * scale);
    const frameCtx = frameCanvas.getContext("2d");
    frameCtx.drawImage(videoEl, 0, 0, frameCanvas.width, frameCanvas.height);

    const response = await fetch(apiUrl("/api/detect_faces"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: frameCanvas.toDataURL("image/jpeg", 0.8) })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.message || data.error || "Face detection request failed");
    }

    faceDetectionAvailable = true;
    faceErrorShown = false;
    drawFaces(data.faces || [], data.width, data.height);
  } catch (err) {
    console.error("Face detection error:", err);
    if (!faceErrorShown) {
      faceErrorShown = true;
      if (streamTrackInterval) {
        clearInterval(streamTrackInterval);
        streamTrackInterval = null;
      }
      botRespond("Camera preview is on, but face detection needs the Flask backend. Deploy the backend and set its URL in config.js.");
    }
  } finally {
    frameRequestPending = false;
  }
}

function drawFaces(faces, imgW, imgH) {
  if (!overlayCtx || !canvasEl || !imgW || !imgH) return;

  canvasEl.width = imgW;
  canvasEl.height = imgH;
  overlayCtx.clearRect(0, 0, imgW, imgH);
  overlayCtx.strokeStyle = "#39e58c";
  overlayCtx.lineWidth = Math.max(2, imgW / 160);
  faces.forEach(face => overlayCtx.strokeRect(face.x, face.y, face.w, face.h));
}

// Wikipedia search function
async function searchWiki(query) {
  try {
    const params = new URLSearchParams({
      action: "query",
      format: "json",
      formatversion: "2",
      generator: "search",
      gsrsearch: query,
      gsrlimit: "1",
      prop: "extracts",
      exintro: "1",
      explaintext: "1",
      origin: "*"
    });
    const response = await fetch(`https://en.wikipedia.org/w/api.php?${params}`);
    if (!response.ok) throw new Error(`Wikipedia returned ${response.status}`);

    const result = await response.json();
    const page = result?.query?.pages?.[0];
    if (!page) {
      botRespond("No Wikipedia results found 🤔");
      return;
    }

    const extract = page.extract || "No summary available.";
    botRespond(`<b>Wikipedia: ${escapeHtml(page.title)}</b><br>${escapeHtml(extract)}`);
  } catch (err) {
    console.error("Wikipedia error:", err);
    botRespond("Could not fetch Wikipedia results. Check your connection and try again.");
  }
}

// Camera stream used by the OpenCV face detection endpoint.
let faceApiCameraStream = null;

// Add fetchNews helper near other network helpers (e.g. after searchWiki)
async function fetchNews(query) {
  botRespond("Checking current affairs feeds…");

  try {
    const res = await fetch(apiUrl("/api/news"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: query })
    });

    const data = await res.json();
    if (!res.ok || data.error) {
      botRespond(data.message || "News feeds could not be reached.");
      return;
    }
    renderNewsResults(data);
  } catch (err) {
    console.error("news fetch error", err);
    botRespond("Could not reach the current affairs service. Check that Flask is running and online.");
  }
}

function renderNewsResults(data) {
  const chatBox = document.getElementById("chatBox");
  const section = document.createElement("section");
  section.className = "message bot news-results";

  const header = document.createElement("header");
  const title = document.createElement("strong");
  title.className = "news-heading";
  title.textContent = "CURRENT AFFAIRS";
  const date = document.createElement("time");
  date.className = "news-date";
  date.dateTime = data.date;
  date.textContent = data.date_label;
  header.append(title, date);
  section.appendChild(header);

  if (data.message) {
    const message = document.createElement("p");
    message.className = "news-status";
    message.textContent = data.message;
    section.appendChild(message);
  }

  (data.categories || []).forEach(category => {
    const group = document.createElement("section");
    group.className = `news-category news-${category.key}`;
    const heading = document.createElement("h3");
    heading.textContent = category.label;
    const count = document.createElement("span");
    count.className = "news-count";
    count.textContent = String(category.articles.length);
    heading.appendChild(count);
    group.appendChild(heading);

    if (!category.articles.length) {
      const empty = document.createElement("p");
      empty.className = "news-empty";
      empty.textContent = "No headlines available for this section and date.";
      group.appendChild(empty);
    }

    category.articles.forEach(article => {
      const card = document.createElement("article");
      card.className = "news-article";
      const headline = document.createElement("h4");
      const safeUrl = /^https:\/\//i.test(article.url || "");
      if (safeUrl) {
        const link = document.createElement("a");
        link.href = article.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = article.title;
        headline.appendChild(link);
      } else {
        headline.textContent = article.title;
      }

      const metadata = document.createElement("p");
      metadata.className = "news-meta";
      const published = new Date(article.published_at);
      const publishedLabel = Number.isNaN(published.getTime())
        ? ""
        : published.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      metadata.textContent = [article.source, publishedLabel].filter(Boolean).join(" · ");
      card.append(headline, metadata);

      if (article.description) {
        const description = document.createElement("p");
        description.className = "news-description";
        description.textContent = article.description;
        card.appendChild(description);
      }
      group.appendChild(card);
    });
    section.appendChild(group);
  });

  chatBox.appendChild(section);
  chatBox.scrollTop = chatBox.scrollHeight;
  botSpeakIfEnabled(`Current affairs for ${data.date_label}. ${data.total} headlines found.`);
}

let pendingCodeFix = null;
let previousCodeFindings = [];

window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("sourceCode").addEventListener("input", () => {
    if (!pendingCodeFix) return;
    pendingCodeFix = null;
    document.getElementById("applyFixesBtn").disabled = true;
    document.getElementById("diffPanel").hidden = true;
    setDebuggerStatus("Source changed; generate a new proposal before applying.");
  });
  document.getElementById("analyzeCodeBtn").addEventListener("click", () => analyzeSubmittedCode());
  document.getElementById("findErrorsBtn").addEventListener("click", () => analyzeSubmittedCode("error"));
  document.getElementById("explainErrorsBtn").addEventListener("click", () => analyzeSubmittedCode());
  document.getElementById("analyzeAgainBtn").addEventListener("click", () => analyzeSubmittedCode());
  document.getElementById("generateFixBtn").addEventListener("click", generateCodeFix);
  document.getElementById("compareCodeBtn").addEventListener("click", showCodeDiff);
  document.getElementById("runTestsBtn").addEventListener("click", runSubmittedCodeTests);
  document.getElementById("applyFixesBtn").addEventListener("click", applyCodeFix);
});

function getCodeWorkbenchInput() {
  return {
    filename: document.getElementById("codeFilename").value.trim() || "snippet.py",
    source: document.getElementById("sourceCode").value
  };
}

async function postCodeWorkbenchRequest(path, payload) {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await response.json().catch(() => ({}));
  if (response.status === 404 && !data.error) {
    data.error = "The Flask API is not available. Deploy the backend and set its URL in config.js.";
  }
  return { response, data };
}

function setDebuggerStatus(message, isError = false) {
  const status = document.getElementById("debuggerStatus");
  status.textContent = message;
  status.classList.toggle("error", isError);
}

function renderCodeFindings(findings) {
  const list = document.getElementById("debuggerFindings");
  list.replaceChildren();
  if (!findings.length) {
    const empty = document.createElement("li");
    empty.className = "finding-empty";
    empty.textContent = "No findings for this analysis.";
    list.appendChild(empty);
    return;
  }

  findings.forEach(finding => {
    const item = document.createElement("li");
    item.className = `finding finding-${finding.severity}`;
    const heading = document.createElement("strong");
    heading.textContent = `${finding.filename}:${finding.line}:${finding.column} · ${finding.title}`;
    const detail = document.createElement("p");
    detail.textContent = finding.explanation;
    const source = document.createElement("small");
    source.textContent = `${finding.code} · ${finding.source}`;
    item.append(heading, detail, source);
    list.appendChild(item);
  });
}

async function analyzeSubmittedCode(severityFilter = null) {
  const input = getCodeWorkbenchInput();
  if (!input.source.trim()) {
    setDebuggerStatus("Paste source code before analysis.", true);
    return;
  }

  setDebuggerStatus("Analyzing source…");
  try {
    const { response, data } = await postCodeWorkbenchRequest("/api/code/analyze", input);
    if (!response.ok) throw new Error(data.error || "Analysis request failed.");
    previousCodeFindings = data.findings || [];
    const visibleFindings = severityFilter
      ? previousCodeFindings.filter(item => item.severity === severityFilter)
      : previousCodeFindings;
    renderCodeFindings(visibleFindings);
    const toolSummary = (data.tools || [])
      .map(tool => `${tool.tool}: ${tool.status}${tool.message ? ` (${tool.message})` : ""}`)
      .join(" · ");
    document.getElementById("debuggerToolStatus").textContent =
      `${data.language} · ${toolSummary || "built-in checks only"} · ${data.ai_review.message}`;
    setDebuggerStatus(`${visibleFindings.length} finding(s) shown.`);
  } catch (error) {
    setDebuggerStatus(error.message || "Could not reach the analysis API.", true);
  }
}

async function generateCodeFix() {
  const input = getCodeWorkbenchInput();
  if (!input.source.trim()) {
    setDebuggerStatus("Paste source code before requesting a proposal.", true);
    return;
  }

  setDebuggerStatus("Checking for a safe syntax repair…");
  try {
    const attempts = Number(document.getElementById("correctionAttempts").value) || 1;
    const { response, data } = await postCodeWorkbenchRequest("/api/code/fix", { ...input, attempts });
    if (!response.ok) throw new Error(data.error || "Could not generate a proposal.");
    pendingCodeFix = data.available ? data.fixed_code : null;
    document.getElementById("applyFixesBtn").disabled = !pendingCodeFix;
    document.getElementById("diffPanel").hidden = !data.available;
    document.getElementById("fixExplanation").textContent =
      `${data.message} ${data.changes.join(" ")} ${data.ai_review.message}`.trim();
    document.getElementById("codeDiff").textContent = data.diff || "No changes proposed.";
    setDebuggerStatus(data.available ? "Proposal ready for review." : data.message, !data.available);
  } catch (error) {
    setDebuggerStatus(error.message || "Could not reach the correction API.", true);
  }
}

function showCodeDiff() {
  if (!pendingCodeFix) {
    setDebuggerStatus("Generate a proposal before comparing code.", true);
    return;
  }
  document.getElementById("diffPanel").hidden = false;
  setDebuggerStatus("Showing the reviewable unified diff.");
}

async function runSubmittedCodeTests() {
  const input = getCodeWorkbenchInput();
  if (!input.source.trim()) {
    setDebuggerStatus("Paste source code before requesting tests.", true);
    return;
  }
  try {
    const { response, data } = await postCodeWorkbenchRequest("/api/code/tests", input);
    if (!response.ok && response.status !== 409) {
      throw new Error(data.error || "Could not reach the test status API.");
    }
    setDebuggerStatus(data.message || "Tests were not run.", true);
  } catch (error) {
    setDebuggerStatus(error.message || "Could not reach the test status API.", true);
  }
}

function applyCodeFix() {
  if (!pendingCodeFix) {
    setDebuggerStatus("There is no reviewed proposal to apply.", true);
    return;
  }

  const input = getCodeWorkbenchInput();
  if (!window.confirm("Apply this reviewed proposal to the editor? A backup will be saved first.")) return;

  const backup = JSON.stringify({ filename: input.filename, source: input.source, createdAt: new Date().toISOString() });
  try {
    sessionStorage.setItem("karenCodeDebuggerBackup", backup);
  } catch (error) {
    setDebuggerStatus("Could not save a browser backup; proposal was not applied.", true);
    return;
  }

  const backupUrl = URL.createObjectURL(new Blob([input.source], { type: "text/plain" }));
  const download = document.createElement("a");
  download.href = backupUrl;
  const backupName = input.filename.split(/[\\/]/).pop().replace(/[<>:"|?*]/g, "_");
  download.download = `${backupName}.bak`;
  download.click();
  setTimeout(() => URL.revokeObjectURL(backupUrl), 1000);

  document.getElementById("sourceCode").value = pendingCodeFix;
  pendingCodeFix = null;
  document.getElementById("applyFixesBtn").disabled = true;
  document.getElementById("diffPanel").hidden = true;
  setDebuggerStatus("Proposal applied to the editor; backup downloaded. Reanalyzing…");
  analyzeSubmittedCode();
}
