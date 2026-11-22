const toggle = document.querySelector("[data-nav-toggle]");
const sidebar = document.querySelector("[data-sidebar]");

if (toggle && sidebar) {
  toggle.addEventListener("click", () => {
    const open = sidebar.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });
}

const status = document.querySelector("[data-status-select]");
const note = document.querySelector("[data-status-note]");

if (status && note) {
  const original = status.dataset.original || "";
  const field = note.closest(".field");
  const markChanged = () => {
    const changed = status.value !== original;
    note.required = changed;
    field?.classList.toggle("is-emphasis", changed);
  };
  status.addEventListener("change", markChanged);
}
