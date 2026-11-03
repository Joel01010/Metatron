// Memory-optimized JARVIS-style overlay for EZSTT.
// No React. No canvas. No WebGL. No permanent 60fps loop while idle.

export interface JarvisHud {
  onState(state: string, detail?: string): void;
  setLevel(rms: number): void;
  setThreshold(rms: number): void;
  setEnabled(on: boolean): void;
  setRecording(on: boolean, startedAtMs?: number): void;
  setMeta(device?: string, model?: string): void;
}

const FLASH_MS: Record<string, number> = {
  INJECTED: 900,
  NOSPEECH: 900,
  NO_MODEL: 1800,
  ERROR: 3500,
};

const LABEL: Record<string, string> = {
  LOADING: "INITIALIZING",
  READY: "NPU ONLINE",
  IDLE: "STANDBY",
  LISTENING: "LISTENING",
  TRANSCRIBING: "TRANSCRIBING",
  INJECTED: "TEXT INJECTED",
  NOSPEECH: "NO SPEECH",
  NO_MODEL: "NO MODEL",
  ERROR: "SYSTEM ERROR",
};

const ACTIVE = new Set(["LISTENING"]);

const HTML = `
<div class="jv asleep" data-state="IDLE">
  <div class="jv-grid"></div>
  <div class="jv-reactor" aria-hidden="true">
    <svg class="jv-rings" viewBox="0 0 180 180">
      <circle class="jv-ring jv-r1" cx="90" cy="90" r="76"/>
      <circle class="jv-ring jv-r2" cx="90" cy="90" r="61"/>
      <circle class="jv-ring jv-r3" cx="90" cy="90" r="47"/>
      <circle class="jv-ring jv-r4" cx="90" cy="90" r="34"/>
      ${Array.from({length: 36}, (_, i) => {
        const a = (i / 36) * Math.PI * 2;
        const x1 = 90 + Math.cos(a) * 67;
        const y1 = 90 + Math.sin(a) * 67;
        const x2 = 90 + Math.cos(a) * 72;
        const y2 = 90 + Math.sin(a) * 72;
        return `<line x1="${x1.toFixed(2)}" y1="${y1.toFixed(2)}" x2="${x2.toFixed(2)}" y2="${y2.toFixed(2)}"/>`;
      }).join("")}
    </svg>
    <div class="jv-core"></div>
  </div>

  <div class="jv-info">
    <div class="jv-kicker"><span class="jv-dot"></span>VOICE INTERFACE</div>
    <div class="jv-status">STANDBY</div>
    <div class="jv-detail"></div>
    <div class="jv-meta">
      <span class="jv-device">NPU</span>
      <span class="jv-sep">/</span>
      <span class="jv-model">MODEL</span>
      <span class="jv-timer"></span>
    </div>
  </div>
</div>`;

function compactModel(raw: string): string {
  const x = raw.split(/[\\/]/).pop() ?? raw;
  return x
    .replace(/^whisper-/, "WHISPER ")
    .replace(/^parakeet-/, "PARAKEET ")
    .replace(/-int8(-ov)?$/i, " INT8")
    .replace(/[-_]+/g, " ")
    .trim()
    .toUpperCase()
    .slice(0, 32);
}

export function mountJarvis(stage: HTMLElement): JarvisHud {
  stage.innerHTML = HTML;
  const root = stage.querySelector<HTMLElement>(".jv")!;
  const core = root.querySelector<HTMLElement>(".jv-core")!;
  const reactor = root.querySelector<HTMLElement>(".jv-reactor")!;
  const statusEl = root.querySelector<HTMLElement>(".jv-status")!;
  const detailEl = root.querySelector<HTMLElement>(".jv-detail")!;
  const deviceEl = root.querySelector<HTMLElement>(".jv-device")!;
  const modelEl = root.querySelector<HTMLElement>(".jv-model")!;
  const timerEl = root.querySelector<HTMLElement>(".jv-timer")!;

  let enabled = true;
  let base = "IDLE";
  let level = 0;
  let threshold = 0.0045;
  let smooth = 0;
  let raf = 0;
  let flashTimer = 0;
  let recording = false;
  let startedAt = 0;
  let timerId = 0;

  function visibleFor(state: string): boolean {
    return (
      state === "LOADING" ||
      state === "LISTENING" ||
      state === "TRANSCRIBING" ||
      state in FLASH_MS ||
      recording
    );
  }

  function setVisible(on: boolean) {
    root.classList.toggle("visible", on && enabled);
    root.classList.toggle("asleep", !(on && enabled));
  }

  function render(state: string, detail = "") {
    root.dataset.state = state;
    statusEl.textContent = LABEL[state] ?? state;
    detailEl.textContent =
      state === "ERROR"
        ? detail.slice(0, 72)
        : state === "TRANSCRIBING"
          ? detail.slice(0, 54)
          : "";
    setVisible(visibleFor(state));
    updateAnimationNeed();
  }

  function audioActive(): boolean {
    return ACTIVE.has(root.dataset.state ?? "") || recording;
  }

  function frame() {
    raf = 0;
    if (!audioActive() || !enabled || !root.classList.contains("visible")) {
      smooth = 0;
      core.style.transform = "";
      reactor.style.transform = "";
      root.style.removeProperty("--jv-amp");
      return;
    }

    const scaled = Math.max(
      0,
      Math.min(1, (level - threshold * 0.45) / Math.max(threshold * 4.0, 0.0001)),
    );
    const target = Math.sqrt(scaled);
    const k = target > smooth ? 0.38 : 0.10;
    smooth += (target - smooth) * k;

    root.style.setProperty("--jv-amp", smooth.toFixed(3));
    core.style.transform = `scale(${(1 + smooth * 0.32).toFixed(3)})`;
    core.style.opacity = String(0.68 + smooth * 0.32);
    reactor.style.transform = `scale(${(1 + smooth * 0.018).toFixed(4)})`;

    raf = requestAnimationFrame(frame);
  }

  function updateAnimationNeed() {
    if (audioActive() && enabled && root.classList.contains("visible")) {
      if (!raf) raf = requestAnimationFrame(frame);
    } else if (raf) {
      cancelAnimationFrame(raf);
      raf = 0;
      smooth = 0;
    }
  }

  function settle() {
    render(base);
  }

  function onState(state: string, detail = "") {
    if (state in FLASH_MS) {
      if (state === "ERROR") base = "IDLE";
      if (flashTimer) clearTimeout(flashTimer);
      render(state, detail);
      flashTimer = window.setTimeout(() => {
        flashTimer = 0;
        settle();
      }, FLASH_MS[state]);
      return;
    }
    base = state;
    if (flashTimer) return;
    render(state, detail);
  }

  function updateTimer() {
    if (!recording) {
      timerEl.textContent = "";
      return;
    }
    const s = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
    const m = Math.floor(s / 60);
    const r = String(s % 60).padStart(2, "0");
    timerEl.textContent = `REC ${m}:${r}`;
  }

  return {
    onState,
    setLevel(rms: number) {
      level = Math.max(0, rms || 0);
    },
    setThreshold(rms: number) {
      threshold = Math.max(0.00001, rms || 0.0045);
    },
    setEnabled(on: boolean) {
      enabled = on;
      if (!enabled) {
        setVisible(false);
      } else {
        settle();
      }
      updateAnimationNeed();
    },
    setRecording(on: boolean, startedAtMs = Date.now()) {
      recording = on;
      root.classList.toggle("recording", on);
      if (on) {
        startedAt = startedAtMs;
        updateTimer();
        if (!timerId) timerId = window.setInterval(updateTimer, 1000);
      } else {
        if (timerId) clearInterval(timerId);
        timerId = 0;
        updateTimer();
      }
      settle();
    },
    setMeta(device = "", model = "") {
      deviceEl.textContent = (device || "DEVICE").toUpperCase();
      modelEl.textContent = model ? compactModel(model) : "MODEL";
    },
  };
}
