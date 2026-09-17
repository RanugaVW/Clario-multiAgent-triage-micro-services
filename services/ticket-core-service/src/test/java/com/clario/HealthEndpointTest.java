package com.clario;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * FR-061 / SUP-004: this service used to expose no health endpoint at all -
 * Spring Security's own SecurityConfig used to permit "/actuator/**" in
 * api-gateway only, and this service had no security filter chain (nor
 * actuator dependency) whatsoever. It now runs a real Spring Boot Actuator
 * health endpoint, reachable without authentication (a health probe from a
 * container orchestrator has no JWT to present), that aggregates real
 * dependency checks (the database, auto-configured by Actuator because a
 * DataSource is present) rather than a hardcoded {"status":"ok"} stub.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class HealthEndpointTest {

    @LocalServerPort
    private int port;

    private final TestRestTemplate restTemplate = new TestRestTemplate();

    @Test
    void healthEndpoint_isReachableWithoutAuthentication_andReportsUp() {
        ResponseEntity<String> response = restTemplate.getForEntity(
                "http://localhost:" + port + "/actuator/health", String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).contains("\"status\":\"UP\"");
        // show-details=never: the response must not name the database, its
        // host, or any other internal component - just the aggregate status.
        assertThat(response.getBody()).doesNotContain("db.mdvfvtpbwqhccmaarpli");
    }

    @Test
    void otherEndpoints_stillRequireAuthentication() {
        ResponseEntity<String> response = restTemplate.getForEntity(
                "http://localhost:" + port + "/api/tickets", String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }
}
