package com.clario.apitest;

import io.restassured.http.ContentType;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;

/**
 * Integration coverage spanning two routes: POST /api/customer_feedback and
 * GET /api/user_tickets - both Next.js (:3000), both against the real,
 * production Supabase project. The signature scenario here is genuinely
 * cross-endpoint: submit feedback through one route, then confirm it shows
 * up nested inside a completely different route's response, proving the
 * two routes actually agree on the same underlying data rather than each
 * being correct in isolation.
 */
class UserTicketsAndFeedbackIntegrationTest {

    @Test
    @DisplayName("GET /api/user_tickets with no auth -> 401")
    void getWithoutAuthIsRejected() {
        given()
                .baseUri(TestFixtures.nextjsUrl())
                .queryParam("userId", TestFixtures.customerAId())
        .when()
                .get("/api/user_tickets")
        .then()
                .statusCode(401);
    }

    @Test
    @DisplayName("GET /api/user_tickets for another customer's id -> 403")
    void getForAnotherCustomerIsForbidden() {
        given()
                .baseUri(TestFixtures.nextjsUrl())
                .header("Authorization", "Bearer " + TestFixtures.tokenB())
                .queryParam("userId", TestFixtures.customerAId())
        .when()
                .get("/api/user_tickets")
        .then()
                .statusCode(403);
    }

    @Test
    @DisplayName("POST /api/customer_feedback with an out-of-range score -> 400")
    void postInvalidScoreIsRejected() {
        given()
                .baseUri(TestFixtures.nextjsUrl())
                .header("Authorization", "Bearer " + TestFixtures.tokenA())
                .contentType(ContentType.JSON)
                .body(Map.of("ticketId", TestFixtures.ticketFeedback(), "score", 7))
        .when()
                .post("/api/customer_feedback")
        .then()
                .statusCode(400);
    }

    @Test
    @DisplayName("Integration: feedback submitted via POST /api/customer_feedback appears nested in GET /api/user_tickets")
    void feedbackSubmissionIsVisibleThroughTheHistoryEndpoint() {
        int score = 4;
        String comment = "RestAssured integration test - " + TestFixtures.marker();

        // Step 1: submit feedback for this ticket, as its owner.
        given()
                .baseUri(TestFixtures.nextjsUrl())
                .header("Authorization", "Bearer " + TestFixtures.tokenA())
                .contentType(ContentType.JSON)
                .body(Map.of("ticketId", TestFixtures.ticketFeedback(), "score", score, "comment", comment))
        .when()
                .post("/api/customer_feedback")
        .then()
                .statusCode(200);

        // Step 2: a completely different route - the customer's own ticket
        // history - must now show this exact score nested under the same
        // ticket, proving both routes read from (and agree on) the same
        // underlying customer_feedback row. Note: customer_feedback comes
        // back as a single nested OBJECT here, not an array like
        // resolutions/ticket_classifications - PostgREST infers a to-one
        // relationship from the ticket_id unique constraint this route's
        // own upsert(..., {onConflict: 'ticket_id'}) relies on. Confirmed
        // against the real response rather than assumed.
        given()
                .baseUri(TestFixtures.nextjsUrl())
                .header("Authorization", "Bearer " + TestFixtures.tokenA())
                .queryParam("userId", TestFixtures.customerAId())
        .when()
                .get("/api/user_tickets")
        .then()
                .statusCode(200)
                .body(
                        "data.find { it.id == '" + TestFixtures.ticketFeedback() + "' }.customer_feedback.score",
                        equalTo(score)
                );
    }

    @Test
    @DisplayName("Someone else's feedback attempt on the same ticket is still rejected after the real feedback exists")
    void anotherCustomersFeedbackAttemptIsForbidden() {
        given()
                .baseUri(TestFixtures.nextjsUrl())
                .header("Authorization", "Bearer " + TestFixtures.tokenB())
                .contentType(ContentType.JSON)
                .body(Map.of("ticketId", TestFixtures.ticketFeedback(), "score", 1))
        .when()
                .post("/api/customer_feedback")
        .then()
                .statusCode(403);
    }
}
