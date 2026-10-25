
/* H&A Service: إشعارات الطلبات الجديدة داخل لوحة الإدارة */
(() => {
  const api = "/admin/api/new-orders";
  const pollEveryMs = 10000;
  let lastSeenId = null;
  let busy = false;

  function ensureNoticeBox() {
    let box = document.getElementById("ha-order-notifications");
    if (box) return box;
    box = document.createElement("div");
    box.id = "ha-order-notifications";
    box.setAttribute("role", "status");
    box.setAttribute("aria-live", "polite");
    Object.assign(box.style, {
      position: "fixed", top: "16px", left: "16px", zIndex: "99999",
      width: "min(360px, calc(100vw - 32px))", display: "grid", gap: "8px"
    });
    document.body.appendChild(box);
    return box;
  }

  function showNotice(order) {
    const box = ensureNoticeBox();
    const card = document.createElement("div");
    Object.assign(card.style, {
      background: "#111", color: "#fff", border: "1px solid #c9a227",
      borderRight: "5px solid #c9a227", borderRadius: "10px", padding: "14px",
      boxShadow: "0 8px 28px rgba(0,0,0,.28)", fontFamily: "Arial,sans-serif",
      direction: "rtl"
    });
    const title = document.createElement("strong");
    title.textContent = `🔔 طلب جديد ${order.order_number}`;
    const details = document.createElement("div");
    details.style.marginTop = "7px";
    details.textContent = `${order.customer_name || "زبون"} — ${order.service || order.category || "خدمة جديدة"}`;
    const close = document.createElement("button");
    close.type = "button";
    close.textContent = "إغلاق";
    Object.assign(close.style, { marginTop: "10px", cursor: "pointer", padding: "5px 10px" });
    close.addEventListener("click", () => card.remove());
    card.append(title, details, close);
    box.prepend(card);
    window.setTimeout(() => card.remove(), 12000);

    // Sound may require a prior click/tap on the page due to browser autoplay rules.
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        const ctx = new AudioCtx();
        const oscillator = ctx.createOscillator();
        const gain = ctx.createGain();
        oscillator.type = "sine";
        oscillator.frequency.value = 880;
        gain.gain.value = 0.07;
        oscillator.connect(gain);
        gain.connect(ctx.destination);
        oscillator.start();
        oscillator.stop(ctx.currentTime + 0.22);
        oscillator.onended = () => ctx.close();
      }
    } catch (_) {}

    if ("Notification" in window && Notification.permission === "granted") {
      try {
        new Notification(`طلب جديد ${order.order_number}`, {
          body: `${order.customer_name || "زبون"} — ${order.service || order.category || "خدمة جديدة"}`
        });
      } catch (_) {}
    }
  }

  async function checkOrders(initial = false) {
    if (busy) return;
    busy = true;
    try {
      const url = lastSeenId === null ? `${api}?after=0` : `${api}?after=${encodeURIComponent(lastSeenId)}`;
      const response = await fetch(url, { credentials: "same-origin", cache: "no-store" });
      if (response.status === 401 || response.redirected) return;
      if (!response.ok) return;
      const data = await response.json();

      // On first page load, establish a baseline and do not alert for old orders.
      if (lastSeenId === null) {
        lastSeenId = Number(data.latest_id || 0);
        return;
      }

      for (const order of data.orders || []) {
        if (Number(order.id) > lastSeenId) showNotice(order);
        lastSeenId = Math.max(lastSeenId, Number(order.id) || 0);
      }
      lastSeenId = Math.max(lastSeenId, Number(data.latest_id) || 0);
    } catch (_) {
      // Temporary network errors are retried at the next polling interval.
    } finally {
      busy = false;
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    checkOrders(true);
    window.setInterval(() => checkOrders(false), pollEveryMs);

    // Ask permission only after an explicit click, to respect browser rules.
    const enableButton = document.getElementById("ha-enable-browser-notifications");
    if (enableButton && "Notification" in window) {
      enableButton.addEventListener("click", async () => {
        try { await Notification.requestPermission(); } catch (_) {}
        enableButton.textContent = Notification.permission === "granted"
          ? "تم تفعيل إشعارات المتصفح" : "لم يتم تفعيل الإشعارات";
      });
    }
  });
})();
