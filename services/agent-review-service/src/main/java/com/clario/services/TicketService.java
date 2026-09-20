package com.clario.services;

import com.clario.entities.Ticket;
import com.clario.repositories.TicketRepository;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.web.client.RestTemplate;

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
    private final TicketDispatcher dispatcher;

    @Transactional
    public Ticket createTicket(String rawText, String subject, UUID userId, String imageBase64) {
        Ticket ticket = new Ticket();
        ticket.setRawText(rawText);
        ticket.setSubject(subject);
        ticket.setUserId(userId);
        ticket.setStatus("received");
        
        Ticket savedTicket = ticketRepository.save(ticket);
        
        // Only enqueue once the ticket is durably committed: enqueueing inside the
        // transaction could hand the AI worker a ticket that isn't visible yet, or
        // leave a queued message for a save that then rolled back.
        afterCommit(() -> dispatcher.submit(
                () -> dispatchToSidecar(savedTicket.getId(), rawText, imageBase64)));

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

    private void dispatchToSidecar(UUID ticketId, String rawText, String imageBase64) {
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
            logger.info("Dispatched ticket {} to Redis queue.", ticketId);
        } catch (Exception e) {
            logger.error("Failed to dispatch ticket {} to Redis queue: {}", ticketId, e.getMessage(), e);
        }
    }
}
