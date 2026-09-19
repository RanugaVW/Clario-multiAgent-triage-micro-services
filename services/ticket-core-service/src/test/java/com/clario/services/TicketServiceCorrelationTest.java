package com.clario.services;

import com.clario.entities.Ticket;
import com.clario.repositories.TicketRepository;
import com.clario.testsupport.CapturingAppender;
import com.clario.tracing.TraceEventPublisher;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.slf4j.MDC;
import org.springframework.data.redis.core.ListOperations;
import org.springframework.data.redis.core.StringRedisTemplate;

import java.time.Duration;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * DC-021: the Redis dispatch runs on another thread. MDC is thread-local, so
 * without explicit propagation a dispatch failure would be logged with no
 * correlation ID - the one log line an operator most needs to tie back to a
 * customer's request.
 */
class TicketServiceCorrelationTest {

    private CapturingAppender serviceLog;
    private TicketDispatcher dispatcher;

    @BeforeEach
    void attach() {
        serviceLog = CapturingAppender.attachTo(TicketService.class);
    }

    @AfterEach
    void detach() {
        serviceLog.detach();
        if (dispatcher != null) {
            dispatcher.stop();
        }
        MDC.clear();
    }

    @SuppressWarnings("unchecked")
    @Test
    void asyncDispatchFailure_isLoggedWithTheCallersCorrelationId() throws Exception {
        TicketRepository repository = mock(TicketRepository.class);
        Ticket saved = new Ticket();
        saved.setId(UUID.randomUUID());
        when(repository.save(any())).thenReturn(saved);

        StringRedisTemplate redis = mock(StringRedisTemplate.class);
        ListOperations<String, String> listOps = mock(ListOperations.class);
        when(redis.opsForList()).thenReturn(listOps);
        when(listOps.leftPush(anyString(), anyString())).thenThrow(new RuntimeException("redis down"));

        dispatcher = new TicketDispatcher(Duration.ofSeconds(2));
        TicketService service = new TicketService(repository, redis, new ObjectMapper(), mock(TraceEventPublisher.class), dispatcher);

        MDC.put("correlationId", "req-async-9");
        service.createTicket("help", "subject", UUID.randomUUID(), null, null);
        MDC.clear();

        long deadline = System.currentTimeMillis() + 5000;
        while (serviceLog.list.isEmpty() && System.currentTimeMillis() < deadline) {
            Thread.sleep(20);
        }

        assertThat(serviceLog.list).isNotEmpty();
        assertThat(serviceLog.list.get(0).getFormattedMessage()).contains("Failed to dispatch");
        assertThat(serviceLog.list.get(0).getMDCPropertyMap()).containsEntry("correlationId", "req-async-9");
    }
}
