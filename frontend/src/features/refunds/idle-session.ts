export const IDLE_WARNING_MS = 15 * 60 * 1000;
export const IDLE_LOGOUT_MS = 20 * 60 * 1000;

type TimeoutApi = Pick<typeof globalThis, "setTimeout" | "clearTimeout">;

export function createIdleSessionController(
  onWarning: () => void,
  onExpiry: () => void,
  timerApi: TimeoutApi = globalThis,
) {
  let warningTimer: ReturnType<typeof setTimeout> | undefined;
  let expiryTimer: ReturnType<typeof setTimeout> | undefined;

  function clear() {
    if (warningTimer !== undefined) timerApi.clearTimeout(warningTimer);
    if (expiryTimer !== undefined) timerApi.clearTimeout(expiryTimer);
    warningTimer = undefined;
    expiryTimer = undefined;
  }

  function reset() {
    clear();
    warningTimer = timerApi.setTimeout(onWarning, IDLE_WARNING_MS);
    expiryTimer = timerApi.setTimeout(onExpiry, IDLE_LOGOUT_MS);
  }

  return { reset, clear };
}
