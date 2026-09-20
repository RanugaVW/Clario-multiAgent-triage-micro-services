package com.clario.testsupport;

import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import org.slf4j.LoggerFactory;

import java.util.List;

/**
 * Captures log events for assertions. Snapshots MDC at log time: Logback reads
 * it lazily otherwise, which would report the (empty) MDC of whichever thread
 * later inspects the event instead of the one that logged it.
 */
public final class CapturingAppender extends ListAppender<ILoggingEvent> {

    private final Logger logger;

    private CapturingAppender(Logger logger) {
        this.logger = logger;
    }

    public static CapturingAppender attachTo(String loggerName) {
        Logger logger = (Logger) LoggerFactory.getLogger(loggerName);
        CapturingAppender appender = new CapturingAppender(logger);
        appender.start();
        logger.addAppender(appender);
        return appender;
    }

    public static CapturingAppender attachTo(Class<?> type) {
        return attachTo(type.getName());
    }

    public void detach() {
        logger.detachAppender(this);
    }

    @Override
    protected void append(ILoggingEvent event) {
        event.prepareForDeferredProcessing();
        super.append(event);
    }

    public List<String> messages() {
        return list.stream().map(ILoggingEvent::getFormattedMessage).toList();
    }
}
