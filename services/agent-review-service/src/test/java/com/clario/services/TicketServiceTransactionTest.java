package com.clario.services;

import com.clario.entities.Ticket;
import com.clario.repositories.TicketRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.core.ListOperations;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.transaction.support.TransactionSynchronizationUtils;

import java.time.Duration;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * REL-011 / REL-004: the queue push must happen only after the ticket row is
 * committed. Enqueueing inside the transaction could give the AI worker a
 * ticket that isn't visible yet, or leave a queued message for a save that
 * then rolled back.
 */
class TicketServiceTransactionTest {

    private ListOperations<String, String> queue;
    private TicketService service;
    private TicketDispatcher dispatcher;

    @SuppressWarnings("unchecked")
    @BeforeEach
    void setUp() {
        TicketRepository repository = mock(TicketRepository.class);
        Ticket saved = new Ticket();
        saved.setId(UUID.randomUUID());
        when(repository.save(any())).thenReturn(saved);

        StringRedisTemplate redis = mock(StringRedisTemplate.class);
        queue = mock(ListOperations.class);
        when(redis.opsForList()).thenReturn(queue);

        // A stopped dispatcher runs work inline, which makes "was it enqueued yet?" deterministic.
        dispatcher = new TicketDispatcher(Duration.ofSeconds(1));
        dispatcher.stop();
        service = new TicketService(repository, redis, new ObjectMapper(), dispatcher);
    }

    @AfterEach
    void cleanUp() {
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.clearSynchronization();
        }
    }

    @Test
    void insideATransaction_nothingIsEnqueued_untilCommit() {
        TransactionSynchronizationManager.initSynchronization();

        service.createTicket("help", "s", UUID.randomUUID(), null);

        verify(queue, never()).leftPush(anyString(), anyString());

        TransactionSynchronizationUtils.triggerAfterCommit();

        verify(queue).leftPush(anyString(), anyString());
    }

    @Test
    void aRolledBackTransaction_neverEnqueuesAGhostMessage() {
        TransactionSynchronizationManager.initSynchronization();

        service.createTicket("help", "s", UUID.randomUUID(), null);
        // Rollback: afterCompletion fires, afterCommit does not.
        TransactionSynchronizationUtils.triggerAfterCompletion(TransactionSynchronization.STATUS_ROLLED_BACK);

        verify(queue, never()).leftPush(anyString(), anyString());
    }

    @Test
    void outsideATransaction_itIsEnqueuedImmediately() {
        service.createTicket("help", "s", UUID.randomUUID(), null);

        verify(queue).leftPush(anyString(), anyString());
    }
}
