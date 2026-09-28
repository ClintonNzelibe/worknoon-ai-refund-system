import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createIdleSessionController,
  IDLE_LOGOUT_MS,
  IDLE_WARNING_MS,
} from "./idle-session";

describe("customer idle session controller", () => {
  afterEach(() => vi.useRealTimers());

  it("shows a warning after 15 minutes and expires after 20 minutes of inactivity", () => {
    vi.useFakeTimers();
    const onWarning = vi.fn();
    const onExpiry = vi.fn();
    const controller = createIdleSessionController(onWarning, onExpiry);

    controller.reset();
    vi.advanceTimersByTime(IDLE_WARNING_MS);
    expect(onWarning).toHaveBeenCalledTimes(1);
    expect(onExpiry).not.toHaveBeenCalled();
    vi.advanceTimersByTime(IDLE_LOGOUT_MS - IDLE_WARNING_MS);
    expect(onExpiry).toHaveBeenCalledTimes(1);
  });

  it("continues the session by resetting both timers", () => {
    vi.useFakeTimers();
    const onWarning = vi.fn();
    const onExpiry = vi.fn();
    const controller = createIdleSessionController(onWarning, onExpiry);

    controller.reset();
    vi.advanceTimersByTime(IDLE_WARNING_MS);
    controller.reset();
    vi.advanceTimersByTime(IDLE_LOGOUT_MS - IDLE_WARNING_MS);
    expect(onExpiry).not.toHaveBeenCalled();
    vi.advanceTimersByTime(IDLE_WARNING_MS);
    expect(onExpiry).toHaveBeenCalledTimes(1);
  });

  it("resets inactivity timing when the application records another interaction", () => {
    vi.useFakeTimers();
    const onWarning = vi.fn();
    const onExpiry = vi.fn();
    const controller = createIdleSessionController(onWarning, onExpiry);

    controller.reset();
    vi.advanceTimersByTime(IDLE_WARNING_MS - 1);
    controller.reset();
    vi.advanceTimersByTime(1);
    expect(onWarning).not.toHaveBeenCalled();
    vi.advanceTimersByTime(IDLE_WARNING_MS - 1);
    expect(onWarning).toHaveBeenCalledTimes(1);
  });
});
