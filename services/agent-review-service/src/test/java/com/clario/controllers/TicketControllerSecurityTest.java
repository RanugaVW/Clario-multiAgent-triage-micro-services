package com.clario.controllers;

import com.clario.config.SecurityConfig;
import com.clario.entities.Ticket;
import com.clario.repositories.TicketRepository;
import com.clario.services.TicketService;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Date;
import java.util.List;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Regression tests for the FR-002 / SEC-002 fix: agent-review-service used to
 * trust a client-supplied X-User-Id header with no verification at all, for
 * both GET and POST. It now requires a signature-verified JWT and derives
 * the caller's identity exclusively from its "sub" claim.
 */
@WebMvcTest(TicketController.class)
@Import(SecurityConfig.class)
class TicketControllerSecurityTest {

    private static final String TEST_SECRET = "test-only-secret-key-for-unit-tests-32bytes-minimum-000000";

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private TicketService ticketService;

    @MockBean
    private TicketRepository ticketRepository;

    private String signedTokenFor(String subject) throws Exception {
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .subject(subject)
                .issueTime(new Date())
                .expirationTime(new Date(System.currentTimeMillis() + 60_000))
                .build();
        SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), claims);
        jwt.sign(new MACSigner(TEST_SECRET));
        return jwt.serialize();
    }

    @Test
    void getTickets_withNoAuthorizationHeader_isRejected() throws Exception {
        mockMvc.perform(get("/api/tickets"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void getTickets_withMalformedToken_isRejected() throws Exception {
        mockMvc.perform(get("/api/tickets").header("Authorization", "Bearer not-a-real-jwt"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void getTickets_withValidToken_usesSubjectFromToken_notSpoofedHeader() throws Exception {
        UUID realUserId = UUID.randomUUID();
        UUID spoofedUserId = UUID.randomUUID();
        String token = signedTokenFor(realUserId.toString());

        when(ticketRepository.findByUserId(realUserId)).thenReturn(List.of(new Ticket()));

        mockMvc.perform(get("/api/tickets")
                        .header("Authorization", "Bearer " + token)
                        // This header used to be trusted outright. It must now be ignored entirely.
                        .header("X-User-Id", spoofedUserId.toString()))
                .andExpect(status().isOk());

        verify(ticketRepository).findByUserId(realUserId);
        verify(ticketRepository, org.mockito.Mockito.never()).findByUserId(spoofedUserId);
    }

    @Test
    void createTicket_withValidToken_createsTicketForSubjectFromToken() throws Exception {
        UUID realUserId = UUID.randomUUID();
        UUID spoofedUserId = UUID.randomUUID();
        String token = signedTokenFor(realUserId.toString());
        Ticket saved = new Ticket();
        saved.setId(UUID.randomUUID());
        when(ticketService.createTicket(any(), any(), any(), any())).thenReturn(saved);

        mockMvc.perform(post("/api/tickets")
                        .header("Authorization", "Bearer " + token)
                        // This header used to be trusted outright for POST too. It must now be ignored.
                        .header("X-User-Id", spoofedUserId.toString())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"rawText\":\"escalated ticket needs review\",\"subject\":\"Review\"}"))
                .andExpect(status().isAccepted());

        verify(ticketService).createTicket(
                org.mockito.ArgumentMatchers.eq("escalated ticket needs review"),
                org.mockito.ArgumentMatchers.eq("Review"),
                org.mockito.ArgumentMatchers.eq(realUserId),
                any());
    }

    @Test
    void createTicket_withNoAuthorizationHeader_isRejected() throws Exception {
        mockMvc.perform(post("/api/tickets")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"rawText\":\"x\",\"subject\":\"y\"}"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void createTicket_withBlankRawText_isRejectedWithDescriptiveError() throws Exception {
        String token = signedTokenFor(UUID.randomUUID().toString());

        mockMvc.perform(post("/api/tickets")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"rawText\":\"\",\"subject\":\"Escalated\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$.error").value("Validation failed"))
                .andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$.details").value(org.hamcrest.Matchers.containsString("rawText")));

        verify(ticketService, org.mockito.Mockito.never()).createTicket(any(), any(), any(), any());
    }

    @Test
    void createTicket_withMissingRawText_isRejectedWithDescriptiveError() throws Exception {
        String token = signedTokenFor(UUID.randomUUID().toString());

        mockMvc.perform(post("/api/tickets")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"subject\":\"Escalated\"}"))
                .andExpect(status().isBadRequest());

        verify(ticketService, org.mockito.Mockito.never()).createTicket(any(), any(), any(), any());
    }

    @Test
    void createTicket_whenDatabaseFails_returns503WithoutLeakingInternals() throws Exception {
        String token = signedTokenFor(UUID.randomUUID().toString());
        when(ticketService.createTicket(any(), any(), any(), any()))
                .thenThrow(new org.springframework.dao.TransientDataAccessResourceException("connection refused: db.internal:5433"));

        mockMvc.perform(post("/api/tickets")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"rawText\":\"help\",\"subject\":\"x\"}"))
                .andExpect(status().isServiceUnavailable())
                .andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$.error")
                        .value(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("db.internal"))));
    }

    @Test
    void getTickets_whenDatabaseFails_returns503() throws Exception {
        UUID realUserId = UUID.randomUUID();
        String token = signedTokenFor(realUserId.toString());
        when(ticketRepository.findByUserId(realUserId))
                .thenThrow(new org.springframework.dao.TransientDataAccessResourceException("connection refused"));

        mockMvc.perform(get("/api/tickets").header("Authorization", "Bearer " + token))
                .andExpect(status().isServiceUnavailable());
    }
}
