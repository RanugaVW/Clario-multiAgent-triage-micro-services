package com.clario.services;

import com.clario.testsupport.CapturingAppender;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.slf4j.MDC;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

import java.time.Duration;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * REL-011: a hand-off a request has already made must survive shutdown, must
 * never be silently dropped, and must not be able to hang shutdown forever.
 */
class TicketDispatcherTest {

    private CapturingAppender log;

    @BeforeEach
    void attach() {
        log = CapturingAppender.attachTo(TicketDispatcher.class);
    }

    @AfterEach
    void detach() {
        log.detach();
        MDC.clear();
    }

    @Test
    void stop_waitsForInFlightWork_beforeReturning() throws Exception {
        TicketDispatcher dispatcher = new TicketDispatcher(Duration.ofSeconds(5));
        CountDownLatch started = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        AtomicBoolean finished = new AtomicBoolean();

        dispatcher.submit(() -> {
            started.countDown();
            await(release);
            finished.set(true);
        });
        assertThat(started.await(2, TimeUnit.SECONDS)).isTrue();

        AtomicBoolean stopReturned = new AtomicBoolean();
        Thread stopper = new Thread(() -> {
            dispatcher.stop();
            stopReturned.set(true);
        });
        stopper.start();

        Thread.sleep(300);
        assertThat(stopReturned).as("stop() must not return while a hand-off is still in flight").isFalse();

        release.countDown();
        stopper.join(3000);
        assertThat(stopReturned).isTrue();
        assertThat(finished).as("the in-flight task ran to completion").isTrue();
    }

    @Test
    void queuedWork_isDrainedToo_notJustTheRunningTask() throws Exception {
        TicketDispatcher dispatcher = new TicketDispatcher(Duration.ofSeconds(5));
        AtomicReference<Integer> completed = new AtomicReference<>(0);
        for (int i = 0; i < 50; i++) {
            dispatcher.submit(() -> {
                sleep(5);
                synchronized (completed) {
                    completed.set(completed.get() + 1);
                }
            });
        }

        dispatcher.stop();

        assertThat(completed.get()).isEqualTo(50);
    }

    @Test
    void workSubmittedAfterStop_runsOnTheCallingThread_insteadOfBeingDropped() {
        TicketDispatcher dispatcher = new TicketDispatcher(Duration.ofSeconds(1));
        dispatcher.stop();
        AtomicReference<String> ranOn = new AtomicReference<>();

        dispatcher.submit(() -> ranOn.set(Thread.currentThread().getName()));

        assertThat(ranOn.get()).isEqualTo(Thread.currentThread().getName());
        assertThat(log.messages()).anyMatch(m -> m.contains("running the task on the calling thread"));
    }

    @Test
    void aTaskThatNeverFinishes_cannotHangShutdown_andIsReported() throws Exception {
        TicketDispatcher dispatcher = new TicketDispatcher(Duration.ofMillis(300));
        CountDownLatch started = new CountDownLatch(1);
        dispatcher.submit(() -> {
            started.countDown();
            await(new CountDownLatch(1)); // never released; only an interrupt ends it
        });
        assertThat(started.await(2, TimeUnit.SECONDS)).isTrue();

        long began = System.nanoTime();
        dispatcher.stop();
        long tookMillis = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - began);

        assertThat(tookMillis).isLessThan(3000);
        assertThat(log.messages()).anyMatch(m -> m.contains("Dispatch drain timed out"));
    }

    @Test
    void theCallersCorrelationId_followsTheTaskToTheWorkerThread() throws Exception {
        TicketDispatcher dispatcher = new TicketDispatcher(Duration.ofSeconds(2));
        AtomicReference<String> seenOnWorker = new AtomicReference<>();
        MDC.put("correlationId", "req-77");

        dispatcher.submit(() -> seenOnWorker.set(MDC.get("correlationId")));
        MDC.clear();
        dispatcher.stop();

        assertThat(seenOnWorker.get()).isEqualTo("req-77");
    }

    @Test
    void oneRequestsCorrelationId_neverLeaksIntoALaterTask() {
        TicketDispatcher dispatcher = new TicketDispatcher(Duration.ofSeconds(2));
        AtomicReference<String> second = new AtomicReference<>("unset");
        MDC.put("correlationId", "first-request");
        dispatcher.submit(() -> { });
        MDC.clear();

        dispatcher.submit(() -> second.set(MDC.get("correlationId")));
        dispatcher.stop();

        assertThat(second.get()).isNull();
    }

    @Test
    void aFailingTask_isLogged_andDoesNotStopLaterWork() {
        TicketDispatcher dispatcher = new TicketDispatcher(Duration.ofSeconds(2));
        AtomicBoolean laterTaskRan = new AtomicBoolean();

        dispatcher.submit(() -> {
            throw new IllegalStateException("boom");
        });
        dispatcher.submit(() -> laterTaskRan.set(true));
        dispatcher.stop();

        assertThat(laterTaskRan).isTrue();
        assertThat(log.messages()).anyMatch(m -> m.contains("Dispatch task failed"));
    }

    @Test
    void closingARealSpringContext_drainsInFlightWork_beforeClosing() throws Exception {
        AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext();
        context.registerBean(TicketDispatcher.class, () -> new TicketDispatcher(Duration.ofSeconds(5)));
        context.refresh();
        TicketDispatcher dispatcher = context.getBean(TicketDispatcher.class);

        CountDownLatch started = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        AtomicBoolean finished = new AtomicBoolean();
        dispatcher.submit(() -> {
            started.countDown();
            await(release);
            finished.set(true);
        });
        assertThat(started.await(2, TimeUnit.SECONDS)).isTrue();

        AtomicBoolean closed = new AtomicBoolean();
        Thread closer = new Thread(() -> {
            context.close();
            closed.set(true);
        });
        closer.start();
        Thread.sleep(300);
        assertThat(closed).as("context.close() must wait for the hand-off").isFalse();

        release.countDown();
        closer.join(3000);
        assertThat(closed).isTrue();
        assertThat(finished).isTrue();
    }

    private static void await(CountDownLatch latch) {
        try {
            latch.await();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private static void sleep(long millis) {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
