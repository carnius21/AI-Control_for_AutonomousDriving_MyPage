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
const sections = [...document.querySelectorAll("main section[id]")].filter(section => section.id !== "home").map(section => {
  const group = navLinks.some(link => link.hash === "#" + section.id) ? section.id : "learning";
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
