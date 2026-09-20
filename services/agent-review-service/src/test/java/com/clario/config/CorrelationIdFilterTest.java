package com.clario.config;

import com.clario.controllers.TicketController;
import com.clario.repositories.TicketRepository;
import com.clario.services.TicketService;
import com.clario.testsupport.CapturingAppender;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * DC-021: a correlation ID must be assigned to every request, appear on the
 * response and in the log lines that request causes, and never leak into a
 * different request or be forgeable through the inbound header.
 */
@WebMvcTest(TicketController.class)
@Import(SecurityConfig.class)
class CorrelationIdFilterTest {

    private static final String UUID_PATTERN =
            "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private TicketService ticketService;

    @MockBean
    private TicketRepository ticketRepository;

    private CapturingAppender audit;

    @BeforeEach
    void attach() {
        audit = CapturingAppender.attachTo(SecurityAuditLogger.LOGGER_NAME);
    }

    @AfterEach
    void detach() {
        audit.detach();
    }

    @Test
    void requestWithoutAnId_getsAGeneratedOne() throws Exception {
        MvcResult result = mockMvc.perform(get("/api/tickets")).andExpect(status().isUnauthorized()).andReturn();

        assertThat(result.getResponse().getHeader(CorrelationIdFilter.HEADER)).matches(UUID_PATTERN);
    }

    @Test
    void aWellFormedInboundId_isHonouredAndEchoedOnce() throws Exception {
        MvcResult result = mockMvc.perform(get("/api/tickets").header(CorrelationIdFilter.HEADER, "abc-123_X.y"))
                .andReturn();

        assertThat(result.getResponse().getHeaders(CorrelationIdFilter.HEADER)).containsExactly("abc-123_X.y");
    }

    @Test
    void aMaliciousInboundId_isReplaced_notEchoedOrLogged() throws Exception {
        String malicious = "abc\r\nX-Injected: 1";

        MvcResult result = mockMvc.perform(get("/api/tickets").header(CorrelationIdFilter.HEADER, malicious))
                .andReturn();

        String echoed = result.getResponse().getHeader(CorrelationIdFilter.HEADER);
        assertThat(echoed).matches(UUID_PATTERN);
        assertThat(audit.list.get(0).getMDCPropertyMap().get(CorrelationIdFilter.MDC_KEY)).matches(UUID_PATTERN);
    }

    @Test
    void anOverlongInboundId_isReplaced() throws Exception {
        MvcResult result = mockMvc.perform(get("/api/tickets").header(CorrelationIdFilter.HEADER, "a".repeat(65)))
                .andReturn();

        assertThat(result.getResponse().getHeader(CorrelationIdFilter.HEADER)).matches(UUID_PATTERN);
    }

    @Test
    void logLinesCausedByTheRequest_carryItsId() throws Exception {
        mockMvc.perform(get("/api/tickets").header(CorrelationIdFilter.HEADER, "trace-me-42"));

        assertThat(audit.list).hasSize(1);
        assertThat(audit.list.get(0).getMDCPropertyMap()).containsEntry(CorrelationIdFilter.MDC_KEY, "trace-me-42");
    }

    @Test
    void theIdDoesNotLeakIntoTheNextRequest_onTheSameThread() throws Exception {
        mockMvc.perform(get("/api/tickets").header(CorrelationIdFilter.HEADER, "first-request"));

        assertThat(MDC.get(CorrelationIdFilter.MDC_KEY)).isNull();

        mockMvc.perform(get("/api/tickets"));
        assertThat(audit.list.get(1).getMDCPropertyMap().get(CorrelationIdFilter.MDC_KEY))
                .isNotEqualTo("first-request");
    }
}
