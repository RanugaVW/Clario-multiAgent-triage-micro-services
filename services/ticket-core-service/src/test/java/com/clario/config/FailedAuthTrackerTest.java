package com.clario.config;

import ch.qos.logback.classic.Level;
import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * SEC-011: repeated authentication failures from one source must raise an
 * alert. Time is driven by a fake clock so window expiry and alert cooldown
 * are asserted exactly, without sleeping.
 */
class FailedAuthTrackerTest {

    /** Mutable clock so tests can move time forward deterministically. */
    static final class FakeClock extends Clock {
        private Instant now = Instant.parse("2026-01-01T00:00:00Z");

        void advance(Duration d) {
            now = now.plus(d);
        }

        @Override
        public ZoneOffset getZone() {
            return ZoneOffset.UTC;
        }

        @Override
        public Clock withZone(java.time.ZoneId zone) {
            return this;
        }

        @Override
        public Instant instant() {
            return now;
        }
    }

    private ListAppender<ILoggingEvent> alerts;
    private Logger alertLogger;
    private FakeClock clock;
    private FailedAuthTracker tracker;

    @BeforeEach
    void setUp() {
        alertLogger = (Logger) LoggerFactory.getLogger(FailedAuthTracker.ALERT_LOGGER_NAME);
        alerts = new ListAppender<>();
        alerts.start();
        alertLogger.addAppender(alerts);
        clock = new FakeClock();
        tracker = new FailedAuthTracker(3, Duration.ofSeconds(60), clock);
    }

    @AfterEach
    void tearDown() {
        alertLogger.detachAppender(alerts);
    }

    private List<String> alertMessages() {
        return alerts.list.stream().map(ILoggingEvent::getFormattedMessage).toList();
    }

    @Test
    void belowThreshold_raisesNoAlert() {
        assertThat(tracker.recordFailure("1.1.1.1")).isFalse();
        assertThat(tracker.recordFailure("1.1.1.1")).isFalse();
        assertThat(alertMessages()).isEmpty();
    }

    @Test
    void reachingThreshold_raisesExactlyOneAlert_atErrorLevel() {
        tracker.recordFailure("1.1.1.1");
        tracker.recordFailure("1.1.1.1");
        assertThat(tracker.recordFailure("1.1.1.1")).isTrue();

        assertThat(alertMessages()).hasSize(1);
        assertThat(alertMessages().get(0))
                .contains("event=SECURITY_ALERT", "type=REPEATED_AUTH_FAILURE", "source=1.1.1.1",
                        "failures=3", "windowSeconds=60");
        assertThat(alerts.list.get(0).getLevel()).isEqualTo(Level.ERROR);
    }

    @Test
    void sustainedAttack_doesNotFloodAlerts_withinOneWindow() {
        for (int i = 0; i < 50; i++) {
            tracker.recordFailure("1.1.1.1");
        }
        assertThat(alertMessages()).hasSize(1);
    }

    @Test
    void attackThatContinuesPastTheWindow_alertsAgain() {
        for (int i = 0; i < 3; i++) {
            tracker.recordFailure("1.1.1.1");
        }
        clock.advance(Duration.ofSeconds(61));
        for (int i = 0; i < 3; i++) {
            tracker.recordFailure("1.1.1.1");
        }
        assertThat(alertMessages()).hasSize(2);
    }

    @Test
    void failuresSpreadOutsideTheWindow_neverAlert() {
        for (int i = 0; i < 10; i++) {
            tracker.recordFailure("1.1.1.1");
            clock.advance(Duration.ofSeconds(40));
        }
        // At most two failures ever fall inside any 60s window (0s and 40s), below the threshold of 3.
        assertThat(alertMessages()).isEmpty();
    }

    @Test
    void sources_areTrackedIndependently() {
        tracker.recordFailure("1.1.1.1");
        tracker.recordFailure("1.1.1.1");
        tracker.recordFailure("2.2.2.2");
        tracker.recordFailure("2.2.2.2");
        assertThat(alertMessages()).isEmpty();

        tracker.recordFailure("2.2.2.2");
        assertThat(alertMessages()).hasSize(1);
        assertThat(alertMessages().get(0)).contains("source=2.2.2.2");
    }

    @Test
    void trackedSources_areBounded_soAFloodOfDistinctSourcesCannotExhaustMemory() {
        FailedAuthTracker bounded = new FailedAuthTracker(3, Duration.ofSeconds(60), clock);
        for (int i = 0; i < FailedAuthTracker.MAX_TRACKED_SOURCES + 500; i++) {
            bounded.recordFailure("10.0." + (i / 250) + "." + (i % 250));
        }
        assertThat(bounded.trackedSources()).isEqualTo(FailedAuthTracker.MAX_TRACKED_SOURCES);
    }

    @Test
    void staleSources_arePurged_whenTheTableIsFull() {
        FailedAuthTracker bounded = new FailedAuthTracker(3, Duration.ofSeconds(60), clock);
        for (int i = 0; i < FailedAuthTracker.MAX_TRACKED_SOURCES; i++) {
            bounded.recordFailure("10.0." + (i / 250) + "." + (i % 250));
        }
        clock.advance(Duration.ofSeconds(120));
        bounded.recordFailure("203.0.113.9");
        assertThat(bounded.trackedSources()).isLessThan(FailedAuthTracker.MAX_TRACKED_SOURCES);
    }

    @Test
    void aFaultInMonitoring_neverPropagatesToTheRequest() {
        Clock exploding = new Clock() {
            @Override
            public java.time.ZoneId getZone() {
                return ZoneOffset.UTC;
            }

            @Override
            public Clock withZone(java.time.ZoneId zone) {
                return this;
            }

            @Override
            public Instant instant() {
                throw new IllegalStateException("clock broke");
            }
        };
        FailedAuthTracker broken = new FailedAuthTracker(3, Duration.ofSeconds(60), exploding);

        assertThat(broken.recordFailure("1.1.1.1")).isFalse();
        assertThat(alertMessages()).hasSize(1);
        assertThat(alertMessages().get(0)).contains("event=SECURITY_MONITOR_ERROR");
    }

    @Test
    void invalidConfiguration_isRejectedAtStartup() {
        assertThatThrownBy(() -> new FailedAuthTracker(0, Duration.ofSeconds(60), clock))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new FailedAuthTracker(3, Duration.ZERO, clock))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
