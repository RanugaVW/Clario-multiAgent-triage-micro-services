package com.clario.services;

import com.clario.entities.Ticket;
import com.clario.repositories.TicketRepository;
import com.clario.tracing.TraceEventPublisher;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.data.redis.core.StringRedisTemplate;
import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class TicketService {

    private static final Logger logger = LoggerFactory.getLogger(TicketService.class);

    private final TicketRepository ticketRepository;
    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final TraceEventPublisher tracePublisher;
    private final TicketDispatcher dispatcher;

    @Transactional
    public Ticket createTicket(String rawText, String subject, UUID userId, String imageBase64, String correlationId) {
        Ticket ticket = new Ticket();
        ticket.setRawText(rawText);
        ticket.setSubject(subject);
        ticket.setUserId(userId);
        ticket.setStatus("received");

        Ticket savedTicket = ticketRepository.save(ticket);
        tracePublisher.publish(savedTicket.getId().toString(), correlationId, "persisted", "done", Map.of());

        // Only enqueue once the ticket is durably committed: enqueueing inside the
        // transaction could hand the AI worker a ticket that isn't visible yet, or
        // leave a queued message for a save that then rolled back.
        afterCommit(() -> dispatcher.submit(
                () -> dispatchToSidecar(savedTicket.getId(), rawText, imageBase64, correlationId)));

        return savedTicket;
    }

    private static void afterCommit(Runnable action) {
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    action.run();
                }
            });
        } else {
            action.run();
        }
    }

    private void dispatchToSidecar(UUID ticketId, String rawText, String imageBase64, String correlationId) {
        try {
            Map<String, String> payload = new java.util.HashMap<>(Map.of(
                    "ticket_id", ticketId.toString(),
                    "raw_text", rawText
            ));
            if (imageBase64 != null) {
                payload.put("image_base64", imageBase64);
            }

            String jsonPayload = objectMapper.writeValueAsString(payload);
            redisTemplate.opsForList().leftPush("ticket_queue", jsonPayload);
            tracePublisher.publish(ticketId.toString(), correlationId, "enqueued", "done", Map.of());
            logger.info("Dispatched ticket {} to Redis queue.", ticketId);
        } catch (Exception e) {
            // REL-002/REL-006: this failure is intentionally swallowed here rather than
            // propagated, since it runs on a fire-and-forget async path after the ticket
            // row is already committed - there's no HTTP response left to fail. It must
            // still be *recorded*, though; a println was not searchable/alertable and
            // gave no operator any way to notice a ticket silently never reached the
            // AI pipeline. This does not yet mark the ticket itself as dispatch-failed
            // (see FR Testing/REL-002-Fault-Tolerance/README.md for that known gap).
            logger.error("Failed to dispatch ticket {} to Redis queue: {}", ticketId, e.getMessage(), e);
        }
    }
}
