package com.clario.config;

import ch.qos.logback.classic.Level;
import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import com.clario.controllers.TicketController;
import com.clario.repositories.TicketRepository;
import com.clario.services.TicketService;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Date;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * FR-049 / SEC-006: authentication and authorization failures used to be
 * answered with a bare 401/403 and nothing else - no record anywhere that an
 * unauthenticated caller had probed the API. These tests assert the audit
 * record exists, carries enough to investigate, and never contains
 * credentials.
 */
@WebMvcTest(TicketController.class)
@Import(SecurityConfig.class)
class SecurityAuditLoggingTest {

    private static final String TEST_SECRET = "test-only-secret-key-for-unit-tests-32bytes-minimum-000000";

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private TicketService ticketService;

    @MockBean
    private TicketRepository ticketRepository;

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

    private String signedTokenFor(String subject) throws Exception {
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .subject(subject)
                .expirationTime(new Date(System.currentTimeMillis() + 60_000))
                .build();
        SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), claims);
        jwt.sign(new MACSigner(TEST_SECRET));
        return jwt.serialize();
    }

    @Test
    void missingToken_isRejectedAndRecorded() throws Exception {
        mockMvc.perform(get("/api/tickets"))
                .andExpect(status().isUnauthorized())
                // The response contract must be unchanged by adding auditing.
                .andExpect(header().exists("WWW-Authenticate"));

        assertThat(auditMessages()).hasSize(1);
        String event = auditMessages().get(0);
        assertThat(event).contains("event=AUTHENTICATION_FAILURE", "method=GET", "path=/api/tickets");
        assertThat(auditEvents.list.get(0).getLevel()).isEqualTo(Level.WARN);
    }

    @Test
    void invalidToken_isRecorded_withoutLeakingTheCredential() throws Exception {
        String secretLookingToken = "supersecret-not-a-jwt-9f8e7d";

        mockMvc.perform(get("/api/tickets").header("Authorization", "Bearer " + secretLookingToken))
                .andExpect(status().isUnauthorized());

        assertThat(auditMessages()).hasSize(1);
        assertThat(auditMessages().get(0)).contains("event=AUTHENTICATION_FAILURE");
        assertThat(auditMessages().get(0)).doesNotContain(secretLookingToken);
    }

    @Test
    void validToken_producesNoAuditFailure() throws Exception {
        String token = signedTokenFor(UUID.randomUUID().toString());

        mockMvc.perform(get("/api/tickets").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk());

        assertThat(auditMessages()).isEmpty();
    }

    @Test
    void accessDenied_isRecordedWithThePrincipal() {
        MockHttpServletRequest request = new MockHttpServletRequest("DELETE", "/api/tickets/42");
        request.setRemoteAddr("10.1.2.3");

        SecurityAuditLogger.accessDenied(request, new org.springframework.security.access.AccessDeniedException("nope"));

        assertThat(auditMessages()).hasSize(1);
        assertThat(auditMessages().get(0))
                .contains("event=ACCESS_DENIED", "method=DELETE", "path=/api/tickets/42",
                        "remote=10.1.2.3", "principal=anonymous");
    }

    @Test
    void attackerControlledValues_cannotForgeAdditionalLogLines() {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/tickets\nevent=ACCESS_GRANTED");

        SecurityAuditLogger.authenticationFailure(request, new RuntimeException("bad\r\ninjected"));

        assertThat(auditMessages()).hasSize(1);
        assertThat(auditMessages().get(0)).doesNotContain("\n").doesNotContain("\r");
    }

    @Test
    void sanitize_truncatesOversizedValues() {
        String longValue = "a".repeat(5000);
        assertThat(SecurityAuditLogger.sanitize(longValue).length()).isLessThan(300);
    }
}
