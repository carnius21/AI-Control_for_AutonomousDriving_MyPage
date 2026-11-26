const video = document.querySelector("#drive-video");
const playback = document.querySelector("#play");
const fullscreen = document.querySelector("#full");
const motion = window.matchMedia("(prefers-reduced-motion: reduce)");

function updatePlaybackLabel() {
  const label = video.paused ? "재생" : "일시정지";
  playback.classList.toggle("playing", !video.paused);
  playback.setAttribute("aria-label", label);
  playback.title = label;
}

function applyMotionPreference() {
  if (motion.matches) video.pause();
  else video.play().catch(updatePlaybackLabel);
}

if (video.canPlayType("video/mp4")) {
  document.querySelector(".controls").hidden = false;
  video.controls = false;
  playback.addEventListener("click", () => {
    if (video.paused) video.play().catch(() => { video.controls = true; });
    else video.pause();
  });
  video.addEventListener("play", updatePlaybackLabel);
  video.addEventListener("pause", updatePlaybackLabel);
  video.addEventListener("error", () => {
    video.controls = true;
    document.querySelector(".controls").hidden = true;
  });
  if (video.requestFullscreen && document.fullscreenEnabled) {
    fullscreen.addEventListener("click", () => video.requestFullscreen().catch(() => { video.controls = true; }));
    document.addEventListener("fullscreenchange", () => { video.controls = document.fullscreenElement === video; });
  } else if (video.webkitEnterFullscreen) {
    fullscreen.addEventListener("click", () => video.webkitEnterFullscreen());
  } else {
    fullscreen.hidden = true;
  }
  motion.addEventListener("change", applyMotionPreference);
  applyMotionPreference();
}

const navLinks = [...document.querySelectorAll(".navlinks a")];
let scrollFrame;
function cancelSectionScroll() {
  cancelAnimationFrame(scrollFrame);
}

function sectionScrollProgress(t) {
  const ramp = 0.25;
  const cruiseSpeed = 1 / (1 - ramp);
  if (t < ramp) return cruiseSpeed * t * t / (2 * ramp);
  if (t <= 1 - ramp) return cruiseSpeed * (t - ramp / 2);
  const remaining = 1 - t;
  return 1 - cruiseSpeed * remaining * remaining / (2 * ramp);
}

for (const link of navLinks.filter(link => link.hash)) {
  link.addEventListener("click", event => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey ||
        event.shiftKey || event.altKey || motion.matches) return;

    const section = document.getElementById(link.hash.slice(1));
    if (!section) return;
    event.preventDefault();
    cancelSectionScroll();
    const root = document.documentElement;
    const start = window.scrollY;
    const inset = parseFloat(getComputedStyle(root).scrollPaddingTop) || 0;
    const end = Math.min(root.scrollHeight - window.innerHeight,
      Math.max(0, start + section.getBoundingClientRect().top - inset));
    const distance = end - start;
    const duration = Math.min(280, 180 + Math.abs(distance) * 0.035);
    const began = performance.now();
    if (location.hash !== link.hash) history.pushState(null, "", link.hash);

    function slide(now) {
      const t = Math.min(1, Math.max(0, (now - began) / duration));
      const eased = sectionScrollProgress(t);
      window.scrollTo(0, start + distance * eased);
      if (t < 1) scrollFrame = requestAnimationFrame(slide);
      else section.focus({preventScroll: true});
    }
    scrollFrame = requestAnimationFrame(slide);
  });
}

for (const type of ["wheel", "touchstart", "pointerdown", "keydown", "popstate", "hashchange"]) {
  window.addEventListener(type, cancelSectionScroll, {passive: true});
}

const sections = [...document.querySelectorAll("main section[id]")].filter(section => section.id !== "home").map(section => {
  const navSection = section.dataset.navSection || section.id;
  const group = navLinks.some(link => link.hash === "#" + navSection) ? navSection : "learning";
  return [group, section];
});
let queued = false;

function updateNavigation() {
  const headerBottom = document.querySelector(".mast").getBoundingClientRect().bottom;
  const anchorOffset = parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0;
  const threshold = Math.max(headerBottom, anchorOffset) + 4;
  let active = "";
  for (const [group, section] of sections) {
    if (section.getBoundingClientRect().top <= threshold) active = group;
  }
  if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) active = "resources";
  for (const link of navLinks) {
    if (link.hash === "#" + active) link.setAttribute("aria-current", "location");
    else link.removeAttribute("aria-current");
  }
  queued = false;
}

function scheduleNavigation() {
  if (!queued) {
    queued = true;
    window.requestAnimationFrame(updateNavigation);
  }
}
window.addEventListener("scroll", scheduleNavigation, {passive: true});
window.addEventListener("resize", scheduleNavigation);
window.addEventListener("load", scheduleNavigation);
updateNavigation();

for (const info of document.querySelectorAll(".driver-info, .term-info")) {
  const button = info.querySelector("button");
  const definition = document.getElementById(button.getAttribute("aria-controls"));
  let pinned = false;

  function showDefinition(open) {
    definition.hidden = !open;
    button.setAttribute("aria-expanded", String(open));
    if (!open) pinned = false;
  }

  info.addEventListener("pointerenter", event => {
    if (event.pointerType === "mouse") showDefinition(true);
  });
  info.addEventListener("pointerleave", () => {
    if (!pinned && !button.matches(":focus-visible")) showDefinition(false);
  });
  button.addEventListener("focus", () => {
    if (button.matches(":focus-visible")) showDefinition(true);
  });
  button.addEventListener("blur", () => showDefinition(false));
  button.addEventListener("click", () => {
    pinned = !pinned;
    showDefinition(pinned);
  });
  document.addEventListener("pointerdown", event => {
    if (!definition.hidden && !info.contains(event.target)) showDefinition(false);
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !definition.hidden) showDefinition(false);
  });
}

const routePicker = document.querySelector(".route-picker");
let selectedFilm;
let filmInView = false;

const filmObserver = new IntersectionObserver((entries) => {
  for (const entry of entries) {
    if (entry.target !== selectedFilm) continue;
    filmInView = entry.intersectionRatio >= 0.25;
    updateRoutePlayback();
  }
}, {threshold: 0.25});

function updateRoutePlayback() {
  if (!selectedFilm) return;
  if (!filmInView || document.hidden || motion.matches) selectedFilm.pause();
  else selectedFilm.play().catch(() => {});
}

function selectRouteFilm() {
  const next = routePicker.querySelector("input:checked + label + figure video");
  if (!next || selectedFilm === next) return;
  if (selectedFilm) {
    selectedFilm.pause();
    filmObserver.unobserve(selectedFilm);
  }
  selectedFilm = next;
  filmInView = false;
  if (next.readyState) next.currentTime = 0;
  filmObserver.observe(next);
}

routePicker.addEventListener("change", selectRouteFilm);
document.addEventListener("visibilitychange", updateRoutePlayback);
motion.addEventListener("change", updateRoutePlayback);
selectRouteFilm();
