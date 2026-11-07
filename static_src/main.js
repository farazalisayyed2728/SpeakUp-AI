import "./main.css";
import Alpine from "alpinejs";
import htmx from "htmx.org";
import { createOrb } from "./orb.js";
import { initTilt } from "./tilt.js";

window.Alpine = Alpine;
window.htmx = htmx;

// Mic demo state machine (Alpine). The browser permission prompt appears only on click.
document.addEventListener("alpine:init", () => {
  Alpine.data("orbDemo", () => ({
    orb: null, on: false, status: "", error: "",
    init() {
      const canvas = this.$refs.canvas;
      this.orb = createOrb(canvas, { onFallback: () => canvas.classList.add("hidden") });
      window.addEventListener("orb:mic-stopped", () => { this.on = false; this.status = "Microphone off."; });
    },
    async toggle() {
      this.error = "";
      if (this.on) { this.orb.disableMic(); return; }
      try {
        await this.orb.enableMic();
        this.on = true;
        this.status = "Listening. Say a sentence and watch the orb. Nothing is recorded or uploaded.";
      } catch (e) {
        this.on = false;
        this.error = e?.name === "NotFoundError"
          ? "No microphone found. Connect one and try again."
          : "Microphone access is blocked. Enable it in your browser's site settings, or keep exploring without it.";
      }
    },
  }));
});

Alpine.start();
initTilt();
