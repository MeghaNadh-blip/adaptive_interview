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
