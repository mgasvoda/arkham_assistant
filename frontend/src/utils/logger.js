/**
 * Frontend logging utility that sends logs to backend.
 */

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

// Generate a session ID for log correlation
const SESSION_ID = `fe-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

// Buffer for batching log entries
let logBuffer = [];
let flushTimer = null;
const FLUSH_INTERVAL = 5000; // 5 seconds
const BATCH_SIZE = 10;

/**
 * Flush buffered logs to the backend.
 */
async function flushLogs() {
  if (logBuffer.length === 0) return;

  const entries = [...logBuffer];
  logBuffer = [];

  try {
    await fetch(`${API_BASE}/logs/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        entries,
        session_id: SESSION_ID,
      }),
    });
  } catch (e) {
    // Silently fail - don't cause more errors from logging
    console.warn('Failed to send logs to backend:', e);
  }
}

/**
 * Schedule a flush if not already scheduled.
 */
function scheduleFlush() {
  if (flushTimer === null) {
    flushTimer = setTimeout(() => {
      flushTimer = null;
      flushLogs();
    }, FLUSH_INTERVAL);
  }

  // Flush immediately if buffer is large
  if (logBuffer.length >= BATCH_SIZE) {
    clearTimeout(flushTimer);
    flushTimer = null;
    flushLogs();
  }
}

/**
 * Add a log entry to the buffer.
 */
function addLogEntry(level, message, options = {}) {
  const entry = {
    level,
    message,
    component: options.component || null,
    error_stack: options.error?.stack || null,
    user_agent: navigator.userAgent,
    url: window.location.href,
    extra: options.extra || null,
  };

  logBuffer.push(entry);
  scheduleFlush();

  // Also log to console in development
  if (import.meta.env.DEV) {
    const consoleFn =
      level === 'error'
        ? console.error
        : level === 'warn'
          ? console.warn
          : level === 'debug'
            ? console.debug
            : console.log;
    consoleFn(`[${level.toUpperCase()}] ${message}`, options);
  }
}

/**
 * Logger object with level methods.
 */
export const logger = {
  debug: (msg, opts) => addLogEntry('debug', msg, opts),
  info: (msg, opts) => addLogEntry('info', msg, opts),
  warn: (msg, opts) => addLogEntry('warn', msg, opts),
  error: (msg, opts) => addLogEntry('error', msg, opts),

  /**
   * Flush any pending logs immediately.
   * Call this before page unload.
   */
  flush: flushLogs,

  /**
   * Get the session ID for this browser session.
   */
  getSessionId: () => SESSION_ID,
};

// Flush logs before page unload
window.addEventListener('beforeunload', flushLogs);

// Capture unhandled errors
window.addEventListener('error', (event) => {
  logger.error(`Unhandled error: ${event.message}`, {
    error: event.error,
    extra: {
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
    },
  });
});

// Capture unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
  logger.error(`Unhandled promise rejection: ${event.reason}`, {
    extra: { reason: String(event.reason) },
  });
});

export default logger;
