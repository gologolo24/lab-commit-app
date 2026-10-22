// Updates the page every few seconds from /api/message (same origin, so it works
// under the strict Content-Security-Policy). The frontend pod itself polls the
// backend every 5 seconds; this only keeps the open browser tab current.
(function () {
  "use strict";
  let interval = 5000;

  function show(data) {
    document.getElementById("greeting").textContent = data.message;
    document.title = data.message;
    document.getElementById("value").textContent = data.value === null ? "-" : String(data.value);
    document.getElementById("fetched").textContent = data.fetched_at || "not yet";
    const status = document.getElementById("status");
    status.textContent = data.backend_ok ? "" : "(backend unavailable, showing the last known value)";
    status.className = data.backend_ok ? "ok" : "stale";
    interval = (data.poll_interval_seconds || 5) * 1000;
  }

  async function refresh() {
    try {
      const response = await fetch("/api/message", { cache: "no-store" });
      if (response.ok) {
        show(await response.json());
      }
    } catch (e) {
      // network hiccup: keep showing the last values
    }
    setTimeout(refresh, interval);
  }

  setTimeout(refresh, interval);
})();
