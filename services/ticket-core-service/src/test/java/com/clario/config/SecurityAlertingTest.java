package com.clario.config;

import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import com.clario.controllers.TicketController;
import com.clario.repositories.TicketRepository;
import com.clario.services.TicketService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * SEC-011 end to end: real rejected requests, through the real security
 * filter chain, must trip the alert - and must still be answered 401.
 */
@WebMvcTest(TicketController.class)
@Import(SecurityConfig.class)
@TestPropertySource(properties = {
        "clario.security.alert.failed-auth-threshold=3",
        "clario.security.alert.window-seconds=60"
})
class SecurityAlertingTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private TicketService ticketService;

    @MockBean
    private TicketRepository ticketRepository;

    private ListAppender<ILoggingEvent> alerts;
    private Logger alertLogger;

    @BeforeEach
    void attach() {
        alertLogger = (Logger) LoggerFactory.getLogger(FailedAuthTracker.ALERT_LOGGER_NAME);
        alerts = new ListAppender<>();
        alerts.start();
        alertLogger.addAppender(alerts);
    }

    @AfterEach
    void detach() {
        alertLogger.detachAppender(alerts);
    }

    private List<String> alertMessages() {
        return alerts.list.stream().map(ILoggingEvent::getFormattedMessage).toList();
    }

    @Test
    void threeRejectedRequests_raiseOneAlert_andEveryResponseIsStillA401() throws Exception {
        // The tracker is a singleton bean shared by every test method in this
        // context, so this test asserts on the alert it provokes itself.
        for (int i = 0; i < 3; i++) {
            mockMvc.perform(get("/api/tickets").header("Authorization", "Bearer bad-token-" + i))
                    .andExpect(status().isUnauthorized());
        }

        assertThat(alertMessages()).hasSize(1);
        assertThat(alertMessages().get(0))
                .contains("event=SECURITY_ALERT", "type=REPEATED_AUTH_FAILURE", "source=127.0.0.1", "failures=3");
        // The alert must describe the source, never the credentials tried.
        assertThat(alertMessages().get(0)).doesNotContain("bad-token");
    }
}
