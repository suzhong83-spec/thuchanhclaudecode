function initSidebarToggle() {
  const sidebar = document.querySelector(".admin-sidebar");
  const backdrop = document.querySelector(".admin-sidebar-backdrop");
  const toggleBtn = document.querySelector(".admin-menu-toggle");

  if (!sidebar || !toggleBtn) return;

  const closeSidebar = () => {
    sidebar.classList.remove("open");
    backdrop?.classList.remove("open");
  };

  toggleBtn.addEventListener("click", () => {
    sidebar.classList.toggle("open");
    backdrop?.classList.toggle("open");
  });

  backdrop?.addEventListener("click", closeSidebar);
}

function initDeleteModals() {
  const modal = document.querySelector(".confirm-modal-overlay");
  if (!modal) return;

  const nameEl = modal.querySelector(".confirm-modal-name");
  const confirmBtn = modal.querySelector(".confirm-modal-confirm");
  const cancelBtn = modal.querySelector(".confirm-modal-cancel");
  let activeForm = null;

  const closeModal = () => {
    modal.classList.remove("open");
    activeForm = null;
  };

  document.querySelectorAll(".js-delete-trigger").forEach((btn) => {
    btn.addEventListener("click", () => {
      activeForm = document.getElementById(btn.dataset.formId);
      if (nameEl) nameEl.textContent = btn.dataset.name || "mục này";
      modal.classList.add("open");
    });
  });

  cancelBtn?.addEventListener("click", closeModal);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });
  confirmBtn?.addEventListener("click", () => {
    if (activeForm) activeForm.submit();
  });
}

function initClickableRows() {
  document.querySelectorAll(".clickable-row").forEach((row) => {
    row.addEventListener("click", (event) => {
      if (event.target.closest("a, button, select, form")) return;
      const href = row.dataset.href;
      if (href) window.location = href;
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initSidebarToggle();
  initDeleteModals();
  initClickableRows();
});
