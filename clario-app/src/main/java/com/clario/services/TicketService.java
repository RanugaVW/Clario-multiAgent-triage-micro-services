package com.clario.services;

import com.clario.entities.Ticket;
import com.clario.repositories.TicketRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestTemplate;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

@Service
@RequiredArgsConstructor
public class TicketService {

    private final TicketRepository ticketRepository;
    private final RestTemplate restTemplate = new RestTemplate();

    @Value("${clario.ml-sidecar.url:http://localhost:8600/process_ticket}")
    private String mlSidecarUrl;

    @Transactional
    public Ticket createTicket(String rawText, String subject, UUID userId, String imageBase64) {
        Ticket ticket = new Ticket();
        ticket.setRawText(rawText);
        ticket.setSubject(subject);
        ticket.setUserId(userId);
        ticket.setStatus("received");
        
        Ticket savedTicket = ticketRepository.save(ticket);
        
        // Dispatch to ML Sidecar asynchronously
        CompletableFuture.runAsync(() -> dispatchToSidecar(savedTicket.getId(), rawText, imageBase64));
        
        return savedTicket;
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
            restTemplate.postForObject(mlSidecarUrl, payload, String.class);
        } catch (Exception e) {
            System.err.println("Failed to dispatch to ML sidecar: " + e.getMessage());
        }
    }
}
