// @ts-check
// Plain JS (TS1: no framework, no bundler). Uses the global Tauri API (app.withGlobalTauri).
const { invoke } = /** @type {any} */ (window).__TAURI__.core;
const $ = (/** @type {string} */ id) => /** @type {HTMLElement} */ (document.getElementById(id));

invoke("core_info").then((p) => ($("core").textContent = p)).catch((e) => ($("core").textContent = String(e)));

$("run").addEventListener("click", async () => {
  const args = /** @type {HTMLTextAreaElement} */ ($("args")).value.split("\n").map((s) => s.trim()).filter(Boolean);
  const started = performance.now();
  $("status").textContent = "Đang chạy…";
  const timer = setInterval(() => {
    $("status").textContent = `Đang chạy… ${((performance.now() - started) / 1000).toFixed(0)} s`;
  }, 1000);
  try {
    const r = await invoke("run_core", { args });
    $("status").textContent = JSON.stringify(r, null, 2);
  } catch (e) {
    $("status").textContent = "Lỗi: " + e;
  } finally {
    clearInterval(timer);
  }
});

$("cancel").addEventListener("click", async () => {
  const ok = await invoke("cancel_core");
  if (!ok) $("status").textContent += "\n(Không có Core nào đang chạy)";
});
