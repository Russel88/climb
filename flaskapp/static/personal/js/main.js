// ts/personal/main.ts
var menuToggle = document.getElementById("menuToggle");
var mobileNav = document.getElementById("mobileNav");
if (menuToggle && mobileNav) {
  menuToggle.addEventListener("click", () => {
    const open = mobileNav.classList.toggle("is-open");
    menuToggle.setAttribute("aria-expanded", String(open));
    mobileNav.setAttribute("aria-hidden", String(!open));
  });
  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    if (!mobileNav.classList.contains("is-open")) {
      return;
    }
    if (mobileNav.contains(target) || menuToggle.contains(target)) {
      return;
    }
    mobileNav.classList.remove("is-open");
    menuToggle.setAttribute("aria-expanded", "false");
    mobileNav.setAttribute("aria-hidden", "true");
  });
}
