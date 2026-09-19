package com.clario.web;

import com.clario.config.CorrelationIdFilter;
import com.clario.config.SecurityAuditLogger;
import com.clario.config.SecurityConfig;
import com.clario.controllers.TicketController;
import com.clario.repositories.TicketRepository;
import com.clario.services.TicketService;
import com.clario.testsupport.CapturingAppender;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.util.Date;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * SUP-005: every error a client sees carries a reference equal to the
 * correlation ID on the matching log lines - and never exposes internals.
 */
@WebMvcTest(TicketController.class)
@Import(SecurityConfig.class)
class ApiExceptionHandlerTest {

    private static final String TEST_SECRET = "test-only-secret-key-for-unit-tests-32bytes-minimum-000000";

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private TicketService ticketService;

    @MockBean
    private TicketRepository ticketRepository;

    private CapturingAppender handlerLog;
    private CapturingAppender audit;

    @BeforeEach
    void attach() {
        handlerLog = CapturingAppender.attachTo(ApiExceptionHandler.class);
        audit = CapturingAppender.attachTo(SecurityAuditLogger.LOGGER_NAME);
    }

    @AfterEach
    void detach() {
        handlerLog.detach();
        audit.detach();
    }

    private String token() throws Exception {
        SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), new JWTClaimsSet.Builder()
                .subject(UUID.randomUUID().toString())
                .expirationTime(new Date(System.currentTimeMillis() + 60_000)).build());
        jwt.sign(new MACSigner(TEST_SECRET));
        return "Bearer " + jwt.serialize();
    }

    private MvcResult submit(String json) throws Exception {
        return mockMvc.perform(post("/api/tickets").header("Authorization", token())
                .header(CorrelationIdFilter.HEADER, "req-ref-77")
                .contentType(MediaType.APPLICATION_JSON).content(json)).andReturn();
    }

    @Test
    void validationFailure_returns400_withDetailsAndTheRequestReference() throws Exception {
        mockMvc.perform(post("/api/tickets").header("Authorization", token())
                        .header(CorrelationIdFilter.HEADER, "req-ref-77")
                        .contentType(MediaType.APPLICATION_JSON).content("{\"rawText\":\"\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("Validation failed"))
                .andExpect(jsonPath("$.details").value(org.hamcrest.Matchers.containsString("rawText")))
                .andExpect(jsonPath("$.reference").value("req-ref-77"));
    }

    @Test
    void databaseFailure_returns503_withReference_andLogsItWithThatReference() throws Exception {
        when(ticketService.createTicket(any(), any(), any(), any(), any()))
                .thenThrow(new org.springframework.dao.TransientDataAccessResourceException("jdbc:postgresql://db.internal:5432 refused"));

        MvcResult result = submit("{\"rawText\":\"help\"}");

        assertThat(result.getResponse().getStatus()).isEqualTo(503);
        assertThat(result.getResponse().getContentAsString())
                .contains("\"reference\":\"req-ref-77\"")
                .doesNotContain("db.internal")
                .doesNotContain("jdbc");
        assertThat(handlerLog.messages()).anyMatch(m -> m.contains("req-ref-77"));
        assertThat(handlerLog.list.get(0).getThrowableProxy()).isNotNull();
    }

    @Test
    void unexpectedException_returns500_genericBody_withReference_andFullDetailOnlyInTheLog() throws Exception {
        when(ticketService.createTicket(any(), any(), any(), any(), any()))
                .thenThrow(new IllegalStateException("secret internal state: password=hunter2"));

        MvcResult result = submit("{\"rawText\":\"help\"}");

        assertThat(result.getResponse().getStatus()).isEqualTo(500);
        String body = result.getResponse().getContentAsString();
        assertThat(body).contains("\"reference\":\"req-ref-77\"");
        assertThat(body).doesNotContain("hunter2").doesNotContain("IllegalStateException");
        assertThat(handlerLog.messages()).anyMatch(m -> m.contains("req-ref-77"));
        assertThat(handlerLog.list.get(0).getThrowableProxy().getMessage()).contains("hunter2");
    }

    @Test
    void securityExceptions_areNotSwallowedInto500_theyStay403_andAreAudited() throws Exception {
        when(ticketService.createTicket(any(), any(), any(), any(), any()))
                .thenThrow(new org.springframework.security.access.AccessDeniedException("not yours"));

        MvcResult result = submit("{\"rawText\":\"help\"}");

        assertThat(result.getResponse().getStatus()).isEqualTo(403);
        assertThat(audit.messages()).anyMatch(m -> m.contains("event=ACCESS_DENIED"));
    }

    @Test
    void malformedJson_keepsItsOwn400_notAGeneric500_andStillGetsAReference() throws Exception {
        MvcResult result = submit("{not json");

        assertThat(result.getResponse().getStatus()).isEqualTo(400);
        assertThat(result.getResponse().getContentAsString()).contains("\"reference\":\"req-ref-77\"");
    }

    @Test
    void wrongHttpMethod_keepsItsOwn405() throws Exception {
        mockMvc.perform(put("/api/tickets").header("Authorization", token())).andExpect(status().isMethodNotAllowed());
    }
}
