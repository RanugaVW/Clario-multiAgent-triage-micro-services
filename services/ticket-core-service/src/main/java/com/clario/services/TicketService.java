package com.clario.services;

import com.clario.entities.Ticket;
import com.clario.repositories.TicketRepository;
import com.clario.tracing.TraceEventPublisher;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.data.redis.core.StringRedisTemplate;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

@Service
@RequiredArgsConstructor
public class TicketService {

    private final TicketRepository ticketRepository;
    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final TraceEventPublisher tracePublisher;

    @Transactional
    public Ticket createTicket(String rawText, String subject, UUID userId, String imageBase64, String correlationId) {
        Ticket ticket = new Ticket();
        ticket.setRawText(rawText);
        ticket.setSubject(subject);
        ticket.setUserId(userId);
        ticket.setStatus("received");

        Ticket savedTicket = ticketRepository.save(ticket);
        tracePublisher.publish(savedTicket.getId().toString(), correlationId, "persisted", "done", Map.of());

        // Dispatch to ML Sidecar asynchronously
        CompletableFuture.runAsync(() -> dispatchToSidecar(savedTicket.getId(), rawText, imageBase64, correlationId));

        return savedTicket;
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
            System.out.println("Dispatched ticket " + ticketId + " to Redis queue.");
        } catch (Exception e) {
            System.err.println("Failed to dispatch to Redis queue: " + e.getMessage());
        }
    }
}
