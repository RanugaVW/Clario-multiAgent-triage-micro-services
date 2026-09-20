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
 * SEC-011 at the edge service: repeated rejected requests from one source
 * must trip the alert, while every response stays a plain 401.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
        "clario.security.alert.failed-auth-threshold=3",
        "clario.security.alert.window-seconds=60"
})
class SecurityAlertingTest {

    @LocalServerPort
    private int port;

    private final TestRestTemplate restTemplate = new TestRestTemplate();

    private ListAppender<ILoggingEvent> alerts;
    private Logger alertLogger;

    @BeforeEach
    void attach() {
        alertLogger = (Logger) LoggerFactory.getLogger(FailedAuthTracker.ALERT_LOGGER_NAME);
        alerts = new ListAppender<>();
        alerts.start();
        alertLogger.addAppender(alerts);
    }

    @AfterEach
    void detach() {
        alertLogger.detachAppender(alerts);
    }

    private List<String> alertMessages() {
        return alerts.list.stream().map(ILoggingEvent::getFormattedMessage).toList();
    }

    @Test
    void threeRejectedRequests_raiseOneAlert_andEveryResponseIsStillA401() {
        for (int i = 0; i < 3; i++) {
            HttpHeaders headers = new HttpHeaders();
            headers.setBearerAuth("bad-token-" + i);
            ResponseEntity<String> response = restTemplate.exchange(
                    "http://localhost:" + port + "/api/tickets", HttpMethod.GET, new HttpEntity<>(headers), String.class);
            assertThat(response.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        }

        assertThat(alertMessages()).hasSize(1);
        assertThat(alertMessages().get(0))
                .contains("event=SECURITY_ALERT", "type=REPEATED_AUTH_FAILURE", "failures=3");
        assertThat(alertMessages().get(0)).doesNotContain("bad-token");
    }
}
