package com.clario.config;

import com.clario.testsupport.CapturingAppender;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;

import static org.assertj.core.api.Assertions.assertThat;

/** DC-021 at the edge: inbound IDs are validated, and log lines carry the request's ID. */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class CorrelationIdFilterTest {

    private static final String UUID_PATTERN = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";

    @LocalServerPort
    private int port;

    private final TestRestTemplate restTemplate = new TestRestTemplate();
    private CapturingAppender audit;

    @BeforeEach
    void attach() {
        audit = CapturingAppender.attachTo(SecurityAuditLogger.LOGGER_NAME);
    }

    @AfterEach
    void detach() {
        audit.detach();
    }

    private ResponseEntity<String> get(String correlationId) {
        HttpHeaders headers = new HttpHeaders();
        if (correlationId != null) {
            headers.add(CorrelationIdFilter.HEADER, correlationId);
        }
        return restTemplate.exchange("http://localhost:" + port + "/api/tickets", HttpMethod.GET,
                new HttpEntity<>(headers), String.class);
    }

    @Test
    void logLinesCausedByTheRequest_carryItsId() {
        get("edge-trace-7");

        assertThat(audit.list).hasSize(1);
        assertThat(audit.list.get(0).getMDCPropertyMap()).containsEntry(CorrelationIdFilter.MDC_KEY, "edge-trace-7");
    }

    @Test
    void anUnsafeInboundId_isReplaced() {
        ResponseEntity<String> response = get("bad id with spaces & <script>");

        assertThat(response.getHeaders().getFirst(CorrelationIdFilter.HEADER)).matches(UUID_PATTERN);
    }

    @Test
    void anOverlongInboundId_isReplaced() {
        ResponseEntity<String> response = get("a".repeat(65));

        assertThat(response.getHeaders().getFirst(CorrelationIdFilter.HEADER)).matches(UUID_PATTERN);
    }
}
