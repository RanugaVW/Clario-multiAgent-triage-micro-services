package com.clario.tracing;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

/**
 * Fire-and-forget publisher for the standalone Ticket Pipeline Tracer relay
 * (Visualizer/relay/ - a separate, non-production process). Disabled by
 * default. See docs/superpowers/specs/2026-09-05-ticket-pipeline-tracer-design.md.
 *
 * Hard constraint: tracing must never slow down or fail real ticket
 * processing. `enabled` is read once at construction, so when disabled the
 * RestTemplate is never invoked at all - not merely suppressed. When
 * enabled, publish() dispatches via CompletableFuture.runAsync so it never
 * blocks the caller's own thread, and any exception inside the async task
 * is caught and logged, never rethrown.
 */
@Component
public class TraceEventPublisher {

    private static final Logger log = LoggerFactory.getLogger(TraceEventPublisher.class);
    private static final String SERVICE_NAME = "api-gateway";

    private final RestTemplate restTemplate;
    private final boolean enabled;
    private final String relayUrl;

    public TraceEventPublisher(
            RestTemplate restTemplate,
            @Value("${clario.tracing.enabled:false}") boolean enabled,
            @Value("${clario.tracing.relay-url:http://localhost:8700}") String relayUrl) {
        this.restTemplate = restTemplate;
        this.enabled = enabled;
        this.relayUrl = relayUrl;
    }

    public void publish(String ticketId, String correlationId, String step, String status, Map<String, Object> detail) {
        if (!enabled) {
            return;
        }
        Map<String, Object> body = new HashMap<>();
        body.put("ticket_id", ticketId);
        body.put("correlation_id", correlationId);
        body.put("service", SERVICE_NAME);
        body.put("step", step);
        body.put("status", status);
        body.put("detail", detail);

        CompletableFuture.runAsync(() -> {
            try {
                restTemplate.postForEntity(relayUrl + "/trace/event", body, Void.class);
            } catch (Exception e) {
                log.debug("Trace event publish failed (relay down/unreachable) - ignored: {}", e.getMessage());
            }
        });
    }
}
