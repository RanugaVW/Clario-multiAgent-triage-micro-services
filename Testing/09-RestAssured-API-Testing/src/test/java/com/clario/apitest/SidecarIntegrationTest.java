package com.clario.apitest;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.hasItem;

/**
 * Integration coverage for the clario-ml-sidecar FastAPI service (:8600) -
 * a different origin entirely from the Next.js routes above, demonstrating
 * REST Assured against both real backends this system exposes.
 */
class SidecarIntegrationTest {

    @Test
    @DisplayName("GET /health -> 200 ok")
    void healthCheck() {
        given()
                .baseUri(TestFixtures.sidecarUrl())
        .when()
                .get("/health")
        .then()
                .statusCode(200)
                .body("status", equalTo("ok"));
    }

    @Test
    @DisplayName("GET /customer_tickets/{userId} with no auth -> 401")
    void getCustomerTicketsWithoutAuthIsRejected() {
        given()
                .baseUri(TestFixtures.sidecarUrl())
        .when()
                .get("/customer_tickets/" + TestFixtures.customerAId())
        .then()
                .statusCode(401);
    }

    @Test
    @DisplayName("Integration: the pre-seeded canary ticket is present in the owner's real ticket list")
    void ownersTicketListIncludesTheSeededTicket() {
        given()
                .baseUri(TestFixtures.sidecarUrl())
                .header("Authorization", "Bearer " + TestFixtures.tokenA())
        .when()
                .get("/customer_tickets/" + TestFixtures.customerAId())
        .then()
                .statusCode(200)
                .body("id", hasItem(TestFixtures.ticketRead()));
    }
}
