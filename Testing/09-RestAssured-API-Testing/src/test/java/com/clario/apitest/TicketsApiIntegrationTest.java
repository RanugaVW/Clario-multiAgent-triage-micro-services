package com.clario.apitest;

import io.restassured.http.ContentType;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.notNullValue;

/**
 * Integration coverage for the staff console's /api/tickets route (Next.js,
 * :3000) - real HTTP calls against the real, live server and production
 * Supabase project, no mocks. Complements Testing/07-API-Testing's Postman
 * suite (per-endpoint contract checks) with a genuine cross-call
 * integration scenario: resolve a ticket via PUT, then read it back via GET
 * and confirm the resolution is actually reflected - not just that the PUT
 * itself returned 200.
 */
class TicketsApiIntegrationTest {

    @Test
    @DisplayName("GET /api/tickets with no auth -> 401")
    void getWithoutAuthIsRejected() {
        given()
                .baseUri(TestFixtures.nextjsUrl())
        .when()
                .get("/api/tickets")
        .then()
                .statusCode(401);
    }

    @Test
    @DisplayName("GET /api/tickets as a customer (non-staff) -> 403")
    void getAsCustomerIsForbidden() {
        given()
                .baseUri(TestFixtures.nextjsUrl())
                .header("Authorization", "Bearer " + TestFixtures.tokenA())
        .when()
                .get("/api/tickets")
        .then()
                .statusCode(403);
    }

    @Test
    @DisplayName("GET /api/tickets as staff -> 200 with a data array")
    void getAsStaffReturnsData() {
        given()
                .baseUri(TestFixtures.nextjsUrl())
                .header("Authorization", "Bearer " + TestFixtures.tokenStaff())
        .when()
                .get("/api/tickets")
        .then()
                .statusCode(200)
                .body("data", notNullValue());
    }

    @Test
    @DisplayName("Integration: PUT resolves a ticket, and the resolution is visible on the very next GET")
    void resolvingATicketIsReflectedOnSubsequentRead() {
        String finalResponse = "RestAssured integration test resolution for " + TestFixtures.marker();

        // Step 1: resolve the ticket.
        given()
                .baseUri(TestFixtures.nextjsUrl())
                .header("Authorization", "Bearer " + TestFixtures.tokenStaff())
                .contentType(ContentType.JSON)
                .body(Map.of("id", TestFixtures.ticketResolve(), "final_response", finalResponse))
        .when()
                .put("/api/tickets")
        .then()
                .statusCode(200)
                .body("success", equalTo(true));

        // Step 2: an independent GET of the full ticket list must now show
        // this exact ticket as resolved, with a matching resolutions[]
        // entry - proving the write actually persisted, not just that the
        // route returned success. Checked against status/escalated rather
        // than final_response: this route's own select() deliberately
        // omits final_response from the nested resolutions object (a
        // lighter list-view payload - the admin console fetches the full
        // text separately per ticket), confirmed by inspecting the real
        // response directly rather than assuming the field would be there.
        given()
                .baseUri(TestFixtures.nextjsUrl())
                .header("Authorization", "Bearer " + TestFixtures.tokenStaff())
        .when()
                .get("/api/tickets")
        .then()
                .statusCode(200)
                .body("data.find { it.id == '" + TestFixtures.ticketResolve() + "' }.status", equalTo("resolved"))
                .body("data.find { it.id == '" + TestFixtures.ticketResolve() + "' }.resolutions[0].escalated", equalTo(false));
    }

    @Test
    @DisplayName("PUT /api/tickets missing final_response -> 400")
    void putMissingFieldIsRejected() {
        given()
                .baseUri(TestFixtures.nextjsUrl())
                .header("Authorization", "Bearer " + TestFixtures.tokenStaff())
                .contentType(ContentType.JSON)
                .body(Map.of("id", TestFixtures.ticketRead()))
        .when()
                .put("/api/tickets")
        .then()
                .statusCode(400);
    }
}
