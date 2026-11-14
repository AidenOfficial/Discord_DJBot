// Applies the pinned theme before the first paint, so the page (and the whole
// Discord Activity "connecting" screen, which shows before App.vue mounts) does
// not flash the OS scheme first. Same storage key ('theme') and attribute
// (data-theme on <html>) as App.vue; App.vue still owns later toggles.
//
// A classic, render-blocking script on purpose (no type=module / defer: those run
// after the first paint). It is a file rather than inline because the CSP only
// allows same-origin scripts. It lives in /assets/ because Flask serves that
// path at both mount points (/ and /app/).
(function () {
  var root = document.documentElement;
  var meta = document.querySelector('meta[name="color-scheme"]');
  var theme = null;
  try {
    theme = window.localStorage.getItem('theme');
  } catch (e) {
    // Site data blocked (third-party iframe, private mode): follow the system.
  }
  if (theme === 'light' || theme === 'dark') {
    root.setAttribute('data-theme', theme);
  } else {
    theme = null;
    // In the Activity on WebKit (Discord iOS) prefers-color-scheme reports the
    // phone setting, not Discord's theme, and Discord gives no theme signal.
    // Chromium (desktop, Android) passes the embedder's scheme through, so it is
    // left alone. Discord defaults to dark. Not persisted: pinning light wins.
    var q = location.search;
    var embedded = /[?&]frame_id=[^&]/.test(q) && /[?&]instance_id=[^&]/.test(q);
    var ua = navigator.userAgent;
    if (embedded && /AppleWebKit\//.test(ua) && !/(Chrome|Chromium)\//.test(ua)) {
      root.setAttribute('data-theme-default', 'dark');
      theme = 'dark';
    }
  }
  if (meta && theme) meta.setAttribute('content', theme);
})();
