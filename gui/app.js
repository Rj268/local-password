const STRONG_LINE_BITS = 75;
const METER_CAP_BITS = 128;

const modeCharacters = document.querySelector("#mode-characters");
const modeWords = document.querySelector("#mode-words");
const characterFields = document.querySelector("#character-fields");
const wordFields = document.querySelector("#word-fields");
const form = document.querySelector("#controls");
const generateButton = document.querySelector("#generate");
const results = document.querySelector("#results");
const strengthLabel = document.querySelector("#strength-label");
const bitsLabel = document.querySelector("#bits-label");
const meterFill = document.querySelector("#meter-fill");
const notes = document.querySelector("#notes");
const statusLine = document.querySelector("#status");
const passwordList = document.querySelector("#password-list");
const copyAllButton = document.querySelector("#copy-all");
const downloadButton = document.querySelector("#download");

const lengthRange = document.querySelector("#length");
const lengthNumber = document.querySelector("#length-number");
const lengthReadout = document.querySelector("#length-readout");
const wordsRange = document.querySelector("#words");
const wordsNumber = document.querySelector("#words-number");
const wordsReadout = document.querySelector("#words-readout");
const countRange = document.querySelector("#count");
const countNumber = document.querySelector("#count-number");
const countReadout = document.querySelector("#count-readout");
const specialInput = document.querySelector("#special");

let mode = "characters";
let busy = false;
let currentPasswords = [];

function bindPair(range, number, readout, rangeMax) {
  const paint = (value) => {
    readout.textContent = String(value);
    range.value = String(Math.min(value, rangeMax));
  };
  range.addEventListener("input", () => {
    number.value = range.value;
    readout.textContent = range.value;
  });
  number.addEventListener("input", () => {
    const value = Number(number.value);
    if (!Number.isFinite(value)) return;
    paint(value);
  });
}

bindPair(lengthRange, lengthNumber, lengthReadout, Number(lengthRange.max));
bindPair(wordsRange, wordsNumber, wordsReadout, Number(wordsRange.max));
bindPair(countRange, countNumber, countReadout, Number(countRange.max));

function setMode(nextMode) {
  mode = nextMode;
  const words = nextMode === "passphrase";
  modeCharacters.setAttribute("aria-selected", String(!words));
  modeWords.setAttribute("aria-selected", String(words));
  characterFields.hidden = words;
  wordFields.hidden = !words;
}

modeCharacters.addEventListener("click", () => {
  if (mode === "characters") return;
  setMode("characters");
  generate();
});

modeWords.addEventListener("click", () => {
  if (mode === "passphrase") return;
  setMode("passphrase");
  generate();
});

function options() {
  return {
    mode,
    length: Number(lengthNumber.value),
    words: Number(wordsNumber.value),
    count: Number(countNumber.value),
    digits: document.querySelector("#digits").checked,
    letters: document.querySelector("#letters").checked,
    special: specialInput.checked,
    allSpecial: specialInput.checked,
    noAmbiguous: false,
  };
}

function setBusy(isBusy) {
  busy = isBusy;
  generateButton.disabled = isBusy;
  generateButton.textContent = isBusy ? "Generating…" : "Generate";
}

function showError(message) {
  statusLine.hidden = false;
  statusLine.className = "status";
  statusLine.textContent = message;
  notes.hidden = true;
  passwordList.replaceChildren();
  currentPasswords = [];
  copyAllButton.disabled = true;
  downloadButton.disabled = true;
  strengthLabel.textContent = "Could not generate";
  bitsLabel.textContent = "";
  meterFill.style.width = "0";
  results.classList.remove("strong", "weak");
}

function renderPassword(password) {
  const item = document.createElement("li");
  item.className = "password";
  const code = document.createElement("code");
  code.textContent = password;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "copy";
  button.textContent = "Copy";
  button.addEventListener("click", () => copyText(password, button));
  item.append(code, button);
  return item;
}

function render(data) {
  statusLine.hidden = true;
  currentPasswords = data.passwords;
  strengthLabel.textContent = data.strong ? "Strong" : "Weak";
  bitsLabel.textContent = `about ${data.bits} bits`;
  results.classList.toggle("strong", data.strong);
  results.classList.toggle("weak", !data.strong);
  const width = Math.max(0, Math.min(100, (data.bits / METER_CAP_BITS) * 100));
  meterFill.style.width = `${width}%`;
  notes.hidden = data.notes.length === 0;
  notes.textContent = data.notes.join(" ");
  passwordList.replaceChildren(...data.passwords.map(renderPassword));
  const hasPassword = data.passwords.length > 0;
  copyAllButton.disabled = !hasPassword;
  downloadButton.disabled = !hasPassword;
}

async function writeClipboard(text) {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_error) {
      /* Fall through to the selection fallback. */
    }
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.left = "-9999px";
  document.body.append(area);
  area.select();
  let copied = false;
  try {
    copied = document.execCommand("copy");
  } catch (_error) {
    copied = false;
  }
  area.remove();
  return copied;
}

async function copyText(text, button) {
  const original = button.textContent;
  const copied = await writeClipboard(text);
  button.textContent = copied ? "Copied" : "Copy failed";
  window.setTimeout(() => {
    button.textContent = original;
  }, 1400);
}

async function generate() {
  if (busy) return;
  setBusy(true);
  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(options()),
    });
    const payload = await response.json();
    if (!response.ok) {
      showError(payload.error || "The generator could not build a password.");
      return;
    }
    render(payload);
  } catch (_error) {
    showError("The local generator is not responding.");
  } finally {
    setBusy(false);
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  generate();
});

copyAllButton.addEventListener("click", () => {
  copyText(currentPasswords.join("\n"), copyAllButton);
});

downloadButton.addEventListener("click", () => {
  const blob = new Blob([currentPasswords.join("\n")], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = currentPasswords.length === 1 ? "password.txt" : "passwords.txt";
  link.click();
  URL.revokeObjectURL(url);
});

document.querySelector("#meter-mark").style.left = `${(STRONG_LINE_BITS / METER_CAP_BITS) * 100}%`;

generate();
