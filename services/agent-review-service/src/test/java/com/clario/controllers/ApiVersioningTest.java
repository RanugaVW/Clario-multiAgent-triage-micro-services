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
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * DC-015 / DC-007: /api/v1/tickets is the versioned contract; the original
 * /api/tickets keeps working but is announced as deprecated; anything else
 * (an unknown version) is not accidentally served.
 */
@WebMvcTest(TicketController.class)
@Import(SecurityConfig.class)
class ApiVersioningTest {

    private static final String TEST_SECRET = "test-only-secret-key-for-unit-tests-32bytes-minimum-000000";

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private TicketService ticketService;

    @MockBean
    private TicketRepository ticketRepository;

    private String bearer(UUID user) throws Exception {
        SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), new JWTClaimsSet.Builder()
                .subject(user.toString()).expirationTime(new Date(System.currentTimeMillis() + 60_000)).build());
        jwt.sign(new MACSigner(TEST_SECRET));
        return "Bearer " + jwt.serialize();
    }

    @Test
    void v1Path_serves_andIsNotFlaggedDeprecated() throws Exception {
        UUID user = UUID.randomUUID();
        when(ticketRepository.findByUserId(user)).thenReturn(List.of(new Ticket()));

        mockMvc.perform(get("/api/v1/tickets").header("Authorization", bearer(user)))
                .andExpect(status().isOk())
                .andExpect(header().doesNotExist("Deprecation"));
    }

    @Test
    void legacyPath_stillServes_butAnnouncesItsSuccessor() throws Exception {
        UUID user = UUID.randomUUID();
        when(ticketRepository.findByUserId(user)).thenReturn(List.of(new Ticket()));

        mockMvc.perform(get("/api/tickets").header("Authorization", bearer(user)))
                .andExpect(status().isOk())
                .andExpect(header().string("Deprecation", "true"))
                .andExpect(header().string("Link", "</api/v1/tickets>; rel=\"successor-version\""));
    }

    @Test
    void theDeprecationSignal_isAlsoOnRejectedRequests() throws Exception {
        // A client failing to authenticate against the old path should still learn where the supported one is.
        mockMvc.perform(get("/api/tickets"))
                .andExpect(status().isUnauthorized())
                .andExpect(header().string("Deprecation", "true"));
    }

    @Test
    void submission_worksOnBothPaths() throws Exception {
        Ticket saved = new Ticket();
        saved.setId(UUID.randomUUID());
        when(ticketService.createTicket(any(), any(), any(), any())).thenReturn(saved);
        String body = "{\"rawText\":\"help\",\"subject\":\"x\"}";
        String auth = bearer(UUID.randomUUID());

        mockMvc.perform(post("/api/v1/tickets").header("Authorization", auth)
                .contentType(MediaType.APPLICATION_JSON).content(body)).andExpect(status().isAccepted());
        mockMvc.perform(post("/api/tickets").header("Authorization", auth)
                .contentType(MediaType.APPLICATION_JSON).content(body)).andExpect(status().isAccepted());
    }

    @Test
    void v1Path_isAuthenticated_likeTheLegacyOne() throws Exception {
        mockMvc.perform(get("/api/v1/tickets")).andExpect(status().isUnauthorized());
    }

    @Test
    void anUnknownVersion_isNotServed() throws Exception {
        mockMvc.perform(get("/api/v2/tickets").header("Authorization", bearer(UUID.randomUUID())))
                .andExpect(status().isNotFound());
    }
}
