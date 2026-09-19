package com.clario;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * REL-011: a request that is in flight when the service is told to stop must be
 * allowed to finish. Runs the real application (all real filters) against a
 * deliberately slow downstream, closes the context mid-request, and observes what the
 * client sees.
 *
 * The control run uses server.shutdown=immediate and must FAIL the same scenario -
 * otherwise a passing graceful run would prove nothing.
 */
class GracefulShutdownTest {

    private static final String SECRET = "test-only-secret-key-for-unit-tests-32bytes-minimum-000000";

    private HttpServer slowDownstream;
    private final CountDownLatch requestReachedDownstream = new CountDownLatch(1);
    private ConfigurableApplicationContext context;

    @BeforeEach
    void startSlowDownstream() throws IOException {
        slowDownstream = HttpServer.create(new InetSocketAddress("localhost", 0), 0);
        slowDownstream.createContext("/", exchange -> {
            requestReachedDownstream.countDown();
            try {
                Thread.sleep(1500); // the "work" that shutdown must not cut short
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            byte[] body = "[\"finished\"]".getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        slowDownstream.start();
    }

    @AfterEach
    void cleanUp() {
        if (context != null && context.isActive()) {
            context.close();
        }
        slowDownstream.stop(0);
    }

    private ConfigurableApplicationContext startGateway(String shutdownMode) {
        return new SpringApplicationBuilder(ClarioApplication.class)
                .properties(
                        "server.port=0",
                        "server.shutdown=" + shutdownMode,
                        "spring.lifecycle.timeout-per-shutdown-phase=10s",
                        "jwt.legacy.secret=" + SECRET,
                        "supabase.jwks.uri=https://example.invalid/auth/v1/.well-known/jwks.json",
                        "management.health.redis.enabled=false",
                        "spring.cloud.gateway.mvc.routes[0].id=slow",
                        "spring.cloud.gateway.mvc.routes[0].uri=http://localhost:" + slowDownstream.getAddress().getPort(),
                        "spring.cloud.gateway.mvc.routes[0].predicates[0]=Path=/api/v1/tickets/**")
                .run();
    }

    /** Returns the client's HTTP status, or -1 if the connection was cut. */
    private int requestDuringShutdown(String shutdownMode) throws Exception {
        context = startGateway(shutdownMode);
        String port = context.getEnvironment().getProperty("local.server.port");

        SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), new JWTClaimsSet.Builder()
                .subject("11111111-1111-1111-1111-111111111111")
                .expirationTime(new Date(System.currentTimeMillis() + 60_000)).build());
        jwt.sign(new MACSigner(SECRET));

        CompletableFuture<Integer> clientResult = CompletableFuture.supplyAsync(() -> {
            try {
                HttpResponse<String> response = HttpClient.newHttpClient().send(
                        HttpRequest.newBuilder(URI.create("http://localhost:" + port + "/api/v1/tickets"))
                                .header("Authorization", "Bearer " + jwt.serialize()).GET().build(),
                        HttpResponse.BodyHandlers.ofString());
                return response.statusCode();
            } catch (Exception e) {
                return -1;
            }
        });

        assertThat(requestReachedDownstream.await(10, TimeUnit.SECONDS)).as("request is in flight").isTrue();
        context.close(); // shutdown begins while the request is still being served
        return clientResult.get(15, TimeUnit.SECONDS);
    }

    @Test
    void gracefulShutdown_letsTheInFlightRequestFinish() throws Exception {
        assertThat(requestDuringShutdown("graceful")).isEqualTo(200);
    }

    @Test
    void control_immediateShutdown_cutsTheSameRequest() throws Exception {
        assertThat(requestDuringShutdown("immediate")).isNotEqualTo(200);
    }
}
