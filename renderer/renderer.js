// ── Constants ──────────────────────────────────────────────────

const CIRCUMFERENCE = 2 * Math.PI * 90; // r=90 in SVG units

const MODES = {
  work:         { name: "Work",         defaultMin: 25, color: "#E53935" },
  short_break:  { name: "Short Break",  defaultMin: 5,  color: "#43A047" },
  long_break:   { name: "Long Break",   defaultMin: 15, color: "#1E88E5" },
};

const IDLE = 0, RUNNING = 1, PAUSED = 2;

// ── State ──────────────────────────────────────────────────────

let state = IDLE;
let mode = "work";
let remaining = MODES.work.defaultMin * 60;
let total = remaining;
let workSessions = 0;
let intervalId = null;

// ── DOM refs ───────────────────────────────────────────────────

const elTime        = document.getElementById("time");
const elModeName    = document.getElementById("mode-name");
const elProgress    = document.getElementById("progress-ring");
const elSessions    = document.getElementById("sessions");
const elBtnStart    = document.getElementById("btn-start");
const elBtnPause    = document.getElementById("btn-pause");
const elBtnReset    = document.getElementById("btn-reset");
const elWorkMin     = document.getElementById("work-min");
const elShortMin    = document.getElementById("short-min");
const elLongMin     = document.getElementById("long-min");
const elOntop       = document.getElementById("ontop-check");

// ── Init ───────────────────────────────────────────────────────

async function init() {
  const config = await window.pomodoro.loadConfig();

  if (config.workMin)        { MODES.work.defaultMin = config.workMin; elWorkMin.value = config.workMin; }
  if (config.shortBreakMin)  { MODES.short_break.defaultMin = config.shortBreakMin; elShortMin.value = config.shortBreakMin; }
  if (config.longBreakMin)   { MODES.long_break.defaultMin = config.longBreakMin; elLongMin.value = config.longBreakMin; }
  if (config.alwaysOnTop != null) { elOntop.checked = config.alwaysOnTop; }

  resetTimer();
  updateDisplay();
}

// ── Timer logic ────────────────────────────────────────────────

function start() {
  if (state === PAUSED) {
    state = RUNNING;
    setControls("running");
    tick();
  } else if (state === IDLE) {
    state = RUNNING;
    setControls("running");
    tick();
  }
}

function pause() {
  if (state === RUNNING) {
    state = PAUSED;
    clearInterval(intervalId);
    setControls("paused");
  }
}

function reset() {
  clearInterval(intervalId);
  state = IDLE;
  resetTimer();
  updateDisplay();
  setControls("idle");
}

function tick() {
  intervalId = setInterval(() => {
    if (remaining <= 0) {
      onComplete();
      return;
    }
    remaining--;
    updateDisplay();
  }, 1000);
}

function onComplete() {
  clearInterval(intervalId);

  // Beep-like notification via system notification
  window.pomodoro.notify({ title: "Time's up!", body: `Starting: ${MODES[mode].name}` });

  if (mode === "work") {
    workSessions++;
    elSessions.textContent = `Completed: ${workSessions} session${workSessions !== 1 ? "s" : ""}`;
    mode = workSessions % 4 === 0 ? "long_break" : "short_break";
  } else {
    mode = "work";
  }

  state = IDLE;
  resetTimer();
  updateDisplay();
  updateModeButtons();
  setControls("idle");
}

function resetTimer() {
  total = MODES[mode].defaultMin * 60;
  remaining = total;
}

// ── Display ────────────────────────────────────────────────────

function updateDisplay() {
  const mins = String(Math.floor(remaining / 60)).padStart(2, "0");
  const secs = String(remaining % 60).padStart(2, "0");
  elTime.textContent = `${mins}:${secs}`;
  elModeName.textContent = MODES[mode].name;

  const ratio = remaining / total;
  const offset = CIRCUMFERENCE * (1 - ratio);
  elProgress.style.strokeDasharray = CIRCUMFERENCE;
  elProgress.style.strokeDashoffset = offset;
  elProgress.style.stroke = MODES[mode].color;

  document.documentElement.style.setProperty("--color-active", MODES[mode].color);
  elModeName.style.color = MODES[mode].color;
}

function updateModeButtons() {
  document.querySelectorAll(".mode-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.mode === mode);
  });
}

function setControls(stateName) {
  if (stateName === "idle") {
    elBtnStart.textContent = "Start";
    elBtnStart.disabled = false;
    elBtnPause.disabled = true;
    elBtnReset.disabled = false;
  } else if (stateName === "running") {
    elBtnStart.disabled = true;
    elBtnPause.textContent = "Pause";
    elBtnPause.disabled = false;
    elBtnReset.disabled = false;
  } else if (stateName === "paused") {
    elBtnStart.textContent = "Resume";
    elBtnStart.disabled = false;
    elBtnPause.disabled = true;
    elBtnReset.disabled = false;
  }
}

// ── Mode switching ─────────────────────────────────────────────

function switchMode(newMode) {
  if (state === RUNNING) {
    if (!confirm("Timer is running. Switch mode and reset?")) return;
    clearInterval(intervalId);
  }

  mode = newMode;
  state = IDLE;
  resetTimer();
  updateDisplay();
  updateModeButtons();
  setControls("idle");
}

// ── Events ─────────────────────────────────────────────────────

elBtnStart.addEventListener("click", start);
elBtnPause.addEventListener("click", pause);
elBtnReset.addEventListener("click", reset);

document.querySelectorAll(".mode-btn").forEach(btn => {
  btn.addEventListener("click", () => switchMode(btn.dataset.mode));
});

document.getElementById("btn-minimize").addEventListener("click", () => {
  window.pomodoro.minimize();
});

document.getElementById("btn-close").addEventListener("click", () => {
  window.pomodoro.saveConfig(buildConfig());
  window.pomodoro.close();
});

document.getElementById("btn-apply").addEventListener("click", () => {
  applySettings();
  window.pomodoro.saveConfig(buildConfig());
});

elOntop.addEventListener("change", () => {
  window.pomodoro.saveConfig(buildConfig());
});

function applySettings() {
  MODES.work.defaultMin = parseInt(elWorkMin.value) || 25;
  MODES.short_break.defaultMin = parseInt(elShortMin.value) || 5;
  MODES.long_break.defaultMin = parseInt(elLongMin.value) || 15;

  if (state === IDLE) {
    resetTimer();
    updateDisplay();
  }
}

function buildConfig() {
  return {
    workMin: parseInt(elWorkMin.value) || 25,
    shortBreakMin: parseInt(elShortMin.value) || 5,
    longBreakMin: parseInt(elLongMin.value) || 15,
    alwaysOnTop: elOntop.checked,
  };
}

// ── Boot ───────────────────────────────────────────────────────

init();
