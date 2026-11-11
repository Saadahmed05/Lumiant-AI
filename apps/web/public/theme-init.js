// Runs before first paint as a same-origin file, so the CSP needs no inline script.
// 1. Applies the theme and rail state, so there is no flash or layout shift. A saved theme wins; with none saved the
//    OS setting decides (light sets [data-theme="light"], dark leaves the attribute off) and is followed live.
// 2. ISSUES #10: background tabs produce no frames, so an entrance animation started there rests at its first
//    keyframe (opacity 0). While hidden, [data-motion="off"] removes entrance animations and every finite running
//    animation is finished; on return, the re-applied entrance animations are finished at once (nothing replays).
(function(){
var root=document.documentElement;
function saved(){try{var t=localStorage.getItem("lumiant-theme");return t==="light"||t==="dark"?t:null}catch{return null}}
var os=window.matchMedia?window.matchMedia("(prefers-color-scheme: light)"):null;
function system(){if(saved())return;if(os&&os.matches)root.dataset.theme="light";else delete root.dataset.theme}
var t=saved();if(t)root.dataset.theme=t;else system();
if(os&&os.addEventListener)os.addEventListener("change",system);
try{if(localStorage.getItem("lumiant-rail")==="collapsed")root.dataset.rail="collapsed"}catch{}
function settle(){try{document.getAnimations().forEach(function(a){var end=a.effect&&a.effect.getComputedTiming().endTime;if(end!==Infinity&&a.playState!=="finished")a.finish()})}catch{}}
function sync(){if(document.visibilityState==="hidden"){root.dataset.motion="off";settle()}else if(root.dataset.motion==="off"){delete root.dataset.motion;settle()}}
sync();document.addEventListener("visibilitychange",sync);
})();
