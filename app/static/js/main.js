// Main Vanilla JS utilities for Adaptive Interview Intelligence
document.addEventListener("DOMContentLoaded", () => {
  // Auto-dismiss alert flashes after 6 seconds
  const flashes = document.querySelectorAll(".flash-message");
  flashes.forEach((f) => {
    setTimeout(() => {
      f.style.opacity = "0";
      f.style.transition = "opacity 0.4s ease";
      setTimeout(() => f.remove(), 400);
    }, 6000);
  });
});


// Accessible responsive navigation for small screens.
document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector(".mobile-nav-toggle");
  const nav = document.getElementById("primary-navigation");
  if (!toggle || !nav) return;
  toggle.addEventListener("click", () => {
    const open = nav.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "Close navigation menu" : "Open navigation menu");
    toggle.textContent = open ? "×" : "☰";
  });
});
