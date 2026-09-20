package com.clario.config;

import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * FR-049 / SEC-006 at the edge service, which is the one actually reachable
 * from outside the Docker network: rejected requests must leave an audit
 * record, and that record must never contain the credential presented.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class SecurityAuditLoggingTest {

    @LocalServerPort
    private int port;

    private final TestRestTemplate restTemplate = new TestRestTemplate();

    private ListAppender<ILoggingEvent> auditEvents;
    private Logger auditLogger;

    @BeforeEach
    void attachAppender() {
        auditLogger = (Logger) LoggerFactory.getLogger(SecurityAuditLogger.LOGGER_NAME);
        auditEvents = new ListAppender<>();
        auditEvents.start();
        auditLogger.addAppender(auditEvents);
    }

    @AfterEach
    void detachAppender() {
        auditLogger.detachAppender(auditEvents);
    }

    private List<String> auditMessages() {
        return auditEvents.list.stream().map(ILoggingEvent::getFormattedMessage).toList();
    }

    @Test
    void missingToken_isRejectedAndRecorded() {
        ResponseEntity<String> response = restTemplate.getForEntity(
                "http://localhost:" + port + "/api/tickets", String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(auditMessages()).hasSize(1);
        assertThat(auditMessages().get(0))
                .contains("event=AUTHENTICATION_FAILURE", "method=GET", "path=/api/tickets");
    }

    @Test
    void invalidToken_isRecorded_withoutLeakingTheCredential() {
        String secretLookingToken = "supersecret-not-a-jwt-9f8e7d";
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(secretLookingToken);

        ResponseEntity<String> response = restTemplate.exchange(
                "http://localhost:" + port + "/api/tickets", HttpMethod.GET, new HttpEntity<>(headers), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(auditMessages()).hasSize(1);
        assertThat(auditMessages().get(0)).contains("event=AUTHENTICATION_FAILURE");
        assertThat(auditMessages().get(0)).doesNotContain(secretLookingToken);
    }

    @Test
    void healthEndpoint_isNotAuditedAsAFailure() {
        ResponseEntity<String> response = restTemplate.getForEntity(
                "http://localhost:" + port + "/actuator/health", String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(auditMessages()).isEmpty();
    }
}
