package com.clario.config;

import com.clario.testsupport.CapturingAppender;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import com.sun.net.httpserver.HttpServer;
import ch.qos.logback.classic.Logger;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import java.io.IOException;
import java.io.InputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Date;
import java.util.Properties;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * DC-021 / SUP-003 at the edge: the gateway must hand its correlation ID to
 * the downstream service (so one ID spans both services' logs), return it to
 * the client exactly once, and no longer print token material to the logs.
 *
 * The downstream is a real local HTTP server, so this exercises the actual
 * Spring Cloud Gateway proxy path rather than assuming header pass-through.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class CorrelationIdPropagationTest {

    private static final String TEST_SECRET = "test-only-secret-key-for-unit-tests-32bytes-minimum-000000";
    private static final String UUID_PATTERN = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";

    private static HttpServer downstream;
    private static final AtomicReference<String> receivedCorrelationId = new AtomicReference<>();

    @BeforeAll
    static void startDownstream() throws IOException {
        downstream = HttpServer.create(new InetSocketAddress("localhost", 0), 0);
        downstream.createContext("/", exchange -> {
            String id = exchange.getRequestHeaders().getFirst(CorrelationIdFilter.HEADER);
            receivedCorrelationId.set(id);
            // A real downstream service echoes the header too - the gateway must not double it.
            exchange.getResponseHeaders().add(CorrelationIdFilter.HEADER, id == null ? "none" : id);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            byte[] body = "[]".getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        downstream.start();
    }

    @AfterAll
    static void stopDownstream() {
        downstream.stop(0);
    }

    @DynamicPropertySource
    static void routeToStub(DynamicPropertyRegistry registry) throws IOException {
        // Started here (not only in @BeforeAll) because property sources are read before it runs.
        if (downstream == null) {
            startDownstream();
        }
        // src/test/resources/application.properties shadows the main one entirely (Spring
        // Boot does not merge them), so the real route isn't present here - define a
        // route to the stub explicitly. What's under test is the filter's behaviour
        // across the proxy hop, not the shipped route table.
        registry.add("spring.cloud.gateway.mvc.routes[0].id", () -> "stub-ticket-core");
        registry.add("spring.cloud.gateway.mvc.routes[0].uri", () -> "http://localhost:" + downstream.getAddress().getPort());
        // The predicate is the one actually shipped in main application.properties, so
        // these tests exercise the real route table's paths against a stub downstream.
        registry.add("spring.cloud.gateway.mvc.routes[0].predicates[0]",
                () -> shippedProperties().getProperty("spring.cloud.gateway.mvc.routes[0].predicates[0]"));
    }


    /**
     * The real main application.properties. The test classpath's own file shadows it (Spring
     * Boot does not merge them), so it is read straight from target/classes.
     */
    private static Properties shippedProperties() {
        try {
            Resource mainFile = Arrays.stream(new PathMatchingResourcePatternResolver().getResources("classpath*:application.properties"))
                    .filter(r -> {
                        try {
                            String url = r.getURL().toString();
                            return url.contains("/classes/") && !url.contains("test-classes");
                        } catch (IOException e) {
                            return false;
                        }
                    }).findFirst().orElseThrow();
            Properties shipped = new Properties();
            try (InputStream in = mainFile.getInputStream()) {
                shipped.load(in);
            }
            return shipped;
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    @LocalServerPort
    private int port;

    private final TestRestTemplate restTemplate = new TestRestTemplate();
    private CapturingAppender everything;

    @BeforeEach
    void attach() {
        receivedCorrelationId.set(null);
        everything = CapturingAppender.attachTo(Logger.ROOT_LOGGER_NAME);
    }

    @AfterEach
    void detach() {
        everything.detach();
    }

    private HttpHeaders authorised() throws Exception {
        SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), new JWTClaimsSet.Builder()
                .subject("11111111-1111-1111-1111-111111111111")
                .expirationTime(new Date(System.currentTimeMillis() + 60_000)).build());
        jwt.sign(new MACSigner(TEST_SECRET));
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(jwt.serialize());
        return headers;
    }

    @Test
    void clientSuppliedId_reachesTheDownstreamService_andComesBackOnce() throws Exception {
        HttpHeaders headers = authorised();
        headers.add(CorrelationIdFilter.HEADER, "gw-trace-1");

        ResponseEntity<String> response = restTemplate.exchange("http://localhost:" + port + "/api/tickets",
                HttpMethod.GET, new HttpEntity<>(headers), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(receivedCorrelationId.get()).isEqualTo("gw-trace-1");
        assertThat(response.getHeaders().get(CorrelationIdFilter.HEADER)).containsExactly("gw-trace-1");
    }

    @Test
    void anIdGeneratedByTheGateway_isTheOneTheDownstreamServiceReceives() throws Exception {
        ResponseEntity<String> response = restTemplate.exchange("http://localhost:" + port + "/api/tickets",
                HttpMethod.GET, new HttpEntity<>(authorised()), String.class);

        String returned = response.getHeaders().getFirst(CorrelationIdFilter.HEADER);
        assertThat(returned).matches(UUID_PATTERN);
        assertThat(receivedCorrelationId.get()).isEqualTo(returned);
    }

    @Test
    void rejectedRequests_alsoGetAnId_sinceTheyAreTheOnesOperatorsInvestigate() {
        ResponseEntity<String> response = restTemplate.getForEntity("http://localhost:" + port + "/api/tickets", String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(response.getHeaders().getFirst(CorrelationIdFilter.HEADER)).matches(UUID_PATTERN);
    }

    @Test
    void tokenMaterial_isNoLongerWrittenToTheLogs() {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth("eyJhbGciOiJIUzI1NiIsImtpZCI6InNlY3JldC1rZXktaWQifQ.payload.sig");

        restTemplate.exchange("http://localhost:" + port + "/api/tickets", HttpMethod.GET, new HttpEntity<>(headers), String.class);

        assertThat(everything.messages()).noneMatch(m -> m.contains("JWT HEADER") || m.contains("secret-key-id"));
    }

    @Test
    void shippedLogConfig_isNotDebugByDefault_andCarriesTheCorrelationId() {
        // Read the real main application.properties from target/classes: the test
        // classpath's own file shadows it, so the Spring Environment can't be used here.
        Properties shipped = shippedProperties();

        assertThat(shipped.getProperty("logging.level.org.springframework.security")).isEqualTo("${LOG_LEVEL_SECURITY:INFO}");
        assertThat(shipped.getProperty("logging.level.org.springframework.cloud.gateway")).isEqualTo("${LOG_LEVEL_GATEWAY:INFO}");
        assertThat(shipped.getProperty("logging.pattern.level")).contains("%X{correlationId");
    }

    @Test
    void shippedRoute_coversTheVersionedPathAndItsDeprecatedAlias() {
        String predicate = shippedProperties().getProperty("spring.cloud.gateway.mvc.routes[0].predicates[0]");
        assertThat(predicate).contains("/api/v1/tickets/**").contains("/api/tickets/**");
    }

    @Test
    void versionedPath_isProxiedToTheTicketService() throws Exception {
        HttpHeaders headers = authorised();
        headers.add(CorrelationIdFilter.HEADER, "v1-trace");

        ResponseEntity<String> response = restTemplate.exchange("http://localhost:" + port + "/api/v1/tickets",
                HttpMethod.GET, new HttpEntity<>(headers), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(receivedCorrelationId.get()).isEqualTo("v1-trace");
    }

    @Test
    void anUnknownVersion_isNotProxied() throws Exception {
        ResponseEntity<String> response = restTemplate.exchange("http://localhost:" + port + "/api/v2/tickets",
                HttpMethod.GET, new HttpEntity<>(authorised()), String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(receivedCorrelationId.get()).isNull();
    }
}
