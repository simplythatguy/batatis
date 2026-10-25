"use strict";
(async () => {
  const api = window.keyDialog;
  const form = document.getElementById("form");
  const input = document.getElementById("key");
  const save = document.getElementById("save");
  const note = document.getElementById("note");
  const info = await api.info();
  if (info && typeof info.label === "string") {
    document.getElementById("label").textContent = info.label;
    document.title = info.label;
  }
  input.focus();
  input.addEventListener("input", () => { save.disabled = input.value.trim().length === 0; note.classList.remove("is-error"); });
  document.getElementById("cancel").addEventListener("click", () => { input.value = ""; void api.cancel(); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") { input.value = ""; void api.cancel(); } });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    save.disabled = true;
    const value = input.value;
    const outcome = await api.submit(value);
    if (outcome === "invalid") {
      note.textContent = "That doesn’t look like an API key. Check it and try again.";
      note.classList.add("is-error");
      save.disabled = false;
      return;
    }
    input.value = "";
  });
})();
