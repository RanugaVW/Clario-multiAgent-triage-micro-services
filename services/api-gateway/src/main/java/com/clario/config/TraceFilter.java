package com.clario.config;

import com.clario.tracing.TraceEventPublisher;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Map;

/**
 * Publishes a "received" trace event for the ticket-submission entry point.
 * The gateway doesn't yet know the real ticket_id (assigned downstream by
 * ticket-core-service) - only the frontend-generated correlation id, read
 * from the X-Trace-Correlation-Id header. Absent whenever tracing is
 * disabled end-to-end, since the frontend only sends it when enabled.
 *
 * Published under the correlation id (not the literal string "unknown") as
 * the ticket_id, so this event lands in the same relay timeline as the
 * frontend's own "submit" event (also keyed by the correlation id) instead
 * of every concurrent ticket's gateway event colliding into one shared
 * "unknown" bucket. The relay folds this into the real ticket_id once
 * ticket-core-service's "persisted" event (which carries both ids) arrives.
 */
@Component
public class TraceFilter extends OncePerRequestFilter {

    private final TraceEventPublisher tracePublisher;

    public TraceFilter(TraceEventPublisher tracePublisher) {
        this.tracePublisher = tracePublisher;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {

        String correlationId = request.getHeader("X-Trace-Correlation-Id");
        if (correlationId != null && "POST".equals(request.getMethod()) && "/api/tickets".equals(request.getRequestURI())) {
            tracePublisher.publish(correlationId, correlationId, "received", "done", Map.of());
        }
        filterChain.doFilter(request, response);
    }
}
