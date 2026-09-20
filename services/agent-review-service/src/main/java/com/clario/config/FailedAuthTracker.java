package com.clario.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Clock;
import java.time.Duration;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

/**
 * SEC-011: "repeated unauthorized access attempts shall be logged" and
 * "security anomalies shall generate administrative alerts". Counts
 * authentication failures per source inside a sliding window and emits one
 * alert record on the dedicated "security.alert" logger when a source reaches
 * the threshold.
 *
 * An alert fires at most once per window per source, so a sustained attack
 * produces a steady trickle rather than a flood. Detection only - it never
 * blocks anything, so a misconfigured threshold cannot lock out real users.
 */
public final class FailedAuthTracker {

    static final String ALERT_LOGGER_NAME = "security.alert";
    static final int MAX_TRACKED_SOURCES = 10_000;

    private static final Logger ALERT = LoggerFactory.getLogger(ALERT_LOGGER_NAME);

    private final int threshold;
    private final Duration window;
    private final Clock clock;
    private final Map<String, SourceWindow> sources = new HashMap<>();

    public FailedAuthTracker(int threshold, Duration window, Clock clock) {
        if (threshold < 1) {
            throw new IllegalArgumentException("threshold must be >= 1");
        }
        if (window.isZero() || window.isNegative()) {
            throw new IllegalArgumentException("window must be positive");
        }
        this.threshold = threshold;
        this.window = window;
        this.clock = clock;
    }

    /**
     * Records a failure and returns true if this failure raised an alert.
     * Never throws: a fault in monitoring must not change how the request
     * that triggered it is answered.
     */
    public synchronized boolean recordFailure(String source) {
        try {
            return doRecordFailure(source);
        } catch (RuntimeException e) {
            ALERT.error("event=SECURITY_MONITOR_ERROR reason={}", e.getClass().getSimpleName());
            return false;
        }
    }

    private boolean doRecordFailure(String source) {
        long now = clock.millis();
        long windowMillis = window.toMillis();

        SourceWindow tracked = sources.get(source);
        if (tracked == null) {
            if (sources.size() >= MAX_TRACKED_SOURCES) {
                purgeStale(now, windowMillis);
            }
            if (sources.size() >= MAX_TRACKED_SOURCES) {
                // Bounded memory beats completeness: a flood of distinct sources
                // must not be able to exhaust the heap. Authentication itself is
                // unaffected - only this counter stops tracking new sources.
                return false;
            }
            tracked = new SourceWindow();
            sources.put(source, tracked);
        }

        while (!tracked.failures.isEmpty() && now - tracked.failures.peekFirst() >= windowMillis) {
            tracked.failures.pollFirst();
        }
        tracked.failures.addLast(now);

        boolean cooledDown = tracked.lastAlertAt == null || now - tracked.lastAlertAt >= windowMillis;
        if (tracked.failures.size() >= threshold && cooledDown) {
            tracked.lastAlertAt = now;
            ALERT.error("event=SECURITY_ALERT type=REPEATED_AUTH_FAILURE source={} failures={} windowSeconds={}",
                    SecurityAuditLogger.sanitize(source), tracked.failures.size(), window.toSeconds());
            return true;
        }
        return false;
    }

    synchronized int trackedSources() {
        return sources.size();
    }

    private void purgeStale(long now, long windowMillis) {
        Iterator<Map.Entry<String, SourceWindow>> it = sources.entrySet().iterator();
        while (it.hasNext()) {
            SourceWindow w = it.next().getValue();
            Long newest = w.failures.peekLast();
            if (newest == null || now - newest >= windowMillis) {
                it.remove();
            }
        }
    }

    private static final class SourceWindow {
        final Deque<Long> failures = new ArrayDeque<>();
        Long lastAlertAt;
    }
}
