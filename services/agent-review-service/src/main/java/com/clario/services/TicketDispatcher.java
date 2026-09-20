package com.clario.services;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.SmartLifecycle;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * REL-011: hands a saved ticket to the Redis queue off the request thread, and
 * makes sure that hand-off is not lost when the service is stopped.
 *
 * Graceful HTTP shutdown only drains *requests*. The queue push is work a
 * request has already handed to another thread, so it needs its own drain:
 * previously it ran on daemon threads, and a deploy could kill the JVM after a
 * ticket was saved and acknowledged (202) but before it was enqueued, leaving a
 * ticket that never reaches the AI pipeline.
 *
 * As a {@link SmartLifecycle} it is stopped by Spring before any bean
 * (Redis connection, datasource) is destroyed, and at phase 0 it stops after
 * the web server's own lifecycle has finished draining requests - so every
 * hand-off those requests made is still pending when the drain starts.
 *
 * Also carries the caller's MDC (correlation ID) onto the worker thread, since
 * MDC is thread-local.
 */
@Component
public class TicketDispatcher implements SmartLifecycle {

    private static final Logger log = LoggerFactory.getLogger(TicketDispatcher.class);

    private final ThreadPoolExecutor executor;
    private final Duration drainTimeout;
    private volatile boolean running = true;

    @Autowired
    public TicketDispatcher(@Value("${clario.dispatch.drain-timeout-seconds:20}") long drainTimeoutSeconds) {
        this(Duration.ofSeconds(drainTimeoutSeconds));
    }

    TicketDispatcher(Duration drainTimeout) {
        this.drainTimeout = drainTimeout;
        AtomicInteger threadNumber = new AtomicInteger();
        // Non-daemon on purpose: the JVM must not be able to exit under queued work.
        // A bounded queue with caller-runs gives backpressure instead of unbounded memory growth.
        this.executor = new ThreadPoolExecutor(4, 4, 30, TimeUnit.SECONDS, new LinkedBlockingQueue<>(1000),
                runnable -> new Thread(runnable, "ticket-dispatch-" + threadNumber.incrementAndGet()),
                new ThreadPoolExecutor.CallerRunsPolicy());
        this.executor.allowCoreThreadTimeOut(true);
    }

    /** Runs the task asynchronously; never silently drops it. */
    public void submit(Runnable task) {
        Map<String, String> callerMdc = MDC.getCopyOfContextMap();
        Runnable wrapped = () -> {
            // With caller-runs this can execute on the request thread: put its MDC back afterwards.
            Map<String, String> previous = MDC.getCopyOfContextMap();
            try {
                if (callerMdc != null) {
                    MDC.setContextMap(callerMdc);
                } else {
                    MDC.clear();
                }
                task.run();
            } catch (RuntimeException e) {
                // A failing task must not take the worker thread down with it.
                log.error("Dispatch task failed", e);
            } finally {
                if (previous != null) {
                    MDC.setContextMap(previous);
                } else {
                    MDC.clear();
                }
            }
        };

        if (!running) {
            // Already stopping: an inline run is slower but the ticket is still enqueued.
            log.warn("Dispatcher is stopping; running the task on the calling thread instead of dropping it");
            wrapped.run();
            return;
        }
        try {
            executor.execute(wrapped);
        } catch (RejectedExecutionException e) {
            wrapped.run();
        }
    }

    @Override
    public void start() {
        running = true;
    }

    @Override
    public void stop() {
        running = false;
        executor.shutdown();
        try {
            if (!executor.awaitTermination(drainTimeout.toMillis(), TimeUnit.MILLISECONDS)) {
                int abandoned = executor.shutdownNow().size();
                log.error("Dispatch drain timed out after {}s; {} queued task(s) abandoned",
                        drainTimeout.toSeconds(), abandoned);
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            executor.shutdownNow();
        }
    }

    @Override
    public boolean isRunning() {
        return running;
    }

    /** Below the web server's shutdown phases, so it stops after in-flight requests have drained. */
    @Override
    public int getPhase() {
        return 0;
    }
}
