/* ============================================================
   Dive Service Management - Main Application JavaScript
   ============================================================ */

/* ---- App Layout (Alpine.js component) ---- */
/* Manages theme toggling (dark/light/auto) and sidebar state.
   Mounted on <body> so state is shared across header, sidebar, and content. */
function appLayout() {
  return {
    // Theme state
    theme: localStorage.getItem('dsm-theme') || 'auto',
    systemPrefersDark: window.matchMedia('(prefers-color-scheme: dark)').matches,

    // Sidebar state
    sidebarOpen: false,       // Mobile: slides sidebar in/out
    sidebarCollapsed: false,  // Desktop: collapse to icons-only

    init() {
      // Listen for system theme changes
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        this.systemPrefersDark = e.matches;
      });
    },

    get effectiveTheme() {
      if (this.theme === 'auto') {
        return this.systemPrefersDark ? 'dark' : 'light';
      }
      return this.theme;
    },

    get themeIcon() {
      if (this.theme === 'dark') return 'bi-moon-stars';
      if (this.theme === 'light') return 'bi-sun';
      return 'bi-circle-half';
    },

    setTheme(newTheme) {
      this.theme = newTheme;
      localStorage.setItem('dsm-theme', newTheme);
    }
  };
}

/* ---- HTMX Configuration ---- */
document.addEventListener('DOMContentLoaded', function () {

  // Add CSRF token to all HTMX requests
  document.body.addEventListener('htmx:configRequest', function (event) {
    var csrfMeta = document.querySelector('meta[name="csrf-token"]');
    if (csrfMeta) {
      event.detail.headers['X-CSRFToken'] = csrfMeta.getAttribute('content');
    }
  });

  // HTMX loading bar
  var loadingBar = document.getElementById('htmx-loading-bar');
  if (loadingBar) {
    document.body.addEventListener('htmx:beforeRequest', function () {
      loadingBar.classList.add('active');
    });
    document.body.addEventListener('htmx:afterRequest', function () {
      loadingBar.classList.remove('active');
    });
  }

  // HTMX error handling
  document.body.addEventListener('htmx:responseError', function (event) {
    console.error('HTMX request failed:', event.detail.xhr.status, event.detail.xhr.statusText);
  });

  // ---- Initialize Bootstrap Tooltips ----
  var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });

  // ---- Initialize Bootstrap Popovers ----
  var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
  popoverTriggerList.map(function (popoverTriggerEl) {
    return new bootstrap.Popover(popoverTriggerEl);
  });

  // ---- Auto-dismiss flash messages after 5 seconds ----
  var flashAlerts = document.querySelectorAll('.alert-dismissible');
  flashAlerts.forEach(function (alert) {
    setTimeout(function () {
      var bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) {
        bsAlert.close();
      }
    }, 5000);
  });
});

/* ---- Notification Polling (Placeholder) ---- */
// Will be implemented in Phase 5 with real notification data.
// The polling interval and endpoint will be configured via data attributes
// on the notification bell element.
function initNotificationPolling() {
  // Placeholder: poll for notifications every 60 seconds
  // var notificationCount = document.getElementById('notificationCount');
  // setInterval(function() {
  //   fetch('/api/notifications/unread-count')
  //     .then(response => response.json())
  //     .then(data => {
  //       if (data.count > 0) {
  //         notificationCount.textContent = data.count;
  //         notificationCount.style.display = '';
  //       } else {
  //         notificationCount.style.display = 'none';
  //       }
  //     })
  //     .catch(err => console.warn('Notification poll failed:', err));
  // }, 60000);
}
