package com.clario;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Date;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * DC-015 / DC-007 / SUP-010: the API contract is generated from the code and
 * pinned by a committed snapshot, so an API change is always a deliberate,
 * reviewable diff instead of silent drift.
 *
 * After an intentional change, regenerate with:
 *   ./mvnw test -Dtest=OpenApiContractTest -Dopenapi.update=true
 * and commit the changed src/test/resources/openapi/ticket-core-service.json.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class OpenApiContractTest {

    private static final String TEST_SECRET = "test-only-secret-key-for-unit-tests-32bytes-minimum-000000";
    private static final Path SNAPSHOT = Path.of("src/test/resources/openapi/ticket-core-service.json");
    private static final ObjectMapper MAPPER = new ObjectMapper();

    @LocalServerPort
    private int port;

    private final TestRestTemplate restTemplate = new TestRestTemplate();
    private JsonNode spec;

    private String token() throws Exception {
        SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), new JWTClaimsSet.Builder()
                .subject("11111111-1111-1111-1111-111111111111")
                .expirationTime(new Date(System.currentTimeMillis() + 60_000)).build());
        jwt.sign(new MACSigner(TEST_SECRET));
        return jwt.serialize();
    }

    @BeforeEach
    void fetchSpec() throws Exception {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(token());
        ResponseEntity<String> response = restTemplate.exchange("http://localhost:" + port + "/v3/api-docs",
                HttpMethod.GET, new HttpEntity<>(headers), String.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        spec = MAPPER.readTree(response.getBody());
        // The server URL embeds the random test port - not part of the contract.
        ((ObjectNode) spec).remove("servers");
    }

    @Test
    void theContractItself_requiresAuthentication_likeEveryOtherEndpoint() {
        ResponseEntity<String> response = restTemplate.getForEntity("http://localhost:" + port + "/v3/api-docs", String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    void onlyTheVersionedPathAndItsDeprecatedAlias_areInTheContract() {
        assertThat(spec.at("/paths").fieldNames()).toIterable()
                .containsExactlyInAnyOrder("/api/v1/tickets", "/api/tickets");
    }

    @Test
    void theUnversionedAlias_isMarkedDeprecated_andTheVersionedPathIsNot() {
        assertThat(spec.at("/paths/~1api~1tickets/get/deprecated").asBoolean()).isTrue();
        assertThat(spec.at("/paths/~1api~1tickets/post/deprecated").asBoolean()).isTrue();
        assertThat(spec.at("/paths/~1api~1tickets/get/description").asText()).contains("/api/v1/tickets");
        assertThat(spec.at("/paths/~1api~1v1~1tickets/get/deprecated").asBoolean()).isFalse();
        assertThat(spec.at("/paths/~1api~1v1~1tickets/post/deprecated").asBoolean()).isFalse();
    }

    @Test
    void noDocumentationUiIsExposed() {
        for (String path : new String[] {"/swagger-ui.html", "/swagger-ui/index.html"}) {
            ResponseEntity<String> response = restTemplate.getForEntity("http://localhost:" + port + path, String.class);
            assertThat(response.getStatusCode()).isIn(HttpStatus.UNAUTHORIZED, HttpStatus.NOT_FOUND);
        }
    }

    @Test
    void ticketEndpoints_areDocumented_withEveryOutcomeAClientMustHandle() {
        JsonNode post = spec.at("/paths/~1api~1v1~1tickets/post/responses");
        assertThat(post.fieldNames()).toIterable().contains("202", "400", "401", "503");
        JsonNode get = spec.at("/paths/~1api~1v1~1tickets/get/responses");
        assertThat(get.fieldNames()).toIterable().contains("200", "401", "503");
    }

    @Test
    void everyOperation_declaresTheBearerRequirement() {
        assertThat(spec.at("/components/securitySchemes/bearerAuth/scheme").asText()).isEqualTo("bearer");
        assertThat(spec.at("/security/0/bearerAuth").isArray()).isTrue();
    }

    @Test
    void theErrorShape_isDocumentedFromTheSameTypeTheHandlersReturn() {
        JsonNode properties = spec.at("/components/schemas/ApiError/properties");
        assertThat(properties.fieldNames()).toIterable().containsExactlyInAnyOrder("error", "reference", "details");
        assertThat(spec.at("/paths/~1api~1v1~1tickets/post/responses/400/content/*~1*/schema/$ref").asText())
                .endsWith("/ApiError");
    }

    @Test
    void validationRules_areVisibleInTheContract_notOnlyInTheCode() {
        JsonNode schema = spec.at("/components/schemas/CreateTicketRequest");
        JsonNode rawText = schema.at("/properties/rawText");
        assertThat(schema.path("required").toString()).contains("rawText");
        assertThat(rawText.path("maxLength").asInt()).isEqualTo(20000);
        // @NotBlank can't be expressed as minLength, so the rule is stated in words.
        assertThat(rawText.path("description").asText()).contains("non-whitespace");
    }

    @Test
    void generatedSpec_matchesTheCommittedSnapshot() throws IOException {
        if (Boolean.getBoolean("openapi.update")) {
            Files.createDirectories(SNAPSHOT.getParent());
            Files.writeString(SNAPSHOT, MAPPER.writerWithDefaultPrettyPrinter().writeValueAsString(spec) + "\n");
            return;
        }
        JsonNode committed = MAPPER.readTree(Files.readString(SNAPSHOT));
        assertThat(spec)
                .as("The API contract changed. If intentional, regenerate the snapshot: "
                        + "./mvnw test -Dtest=OpenApiContractTest -Dopenapi.update=true")
                .isEqualTo(committed);
    }
}
