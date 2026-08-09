package com.clario.controllers;

import com.clario.entities.Ticket;
import com.clario.repositories.TicketRepository;
import com.clario.services.TicketService;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/tickets")
@RequiredArgsConstructor
public class TicketController {

    private final TicketService ticketService;
    private final TicketRepository ticketRepository;

    @GetMapping
    public ResponseEntity<List<Ticket>> getUserTickets(@RequestHeader(value = "X-User-Id", required = false) String userId) {
        if (userId == null) {
            userId = "00000000-0000-0000-0000-000000000000"; // fallback
        }
        return ResponseEntity.ok(ticketRepository.findByUserId(UUID.fromString(userId)));
    }

    @PostMapping
    public ResponseEntity<Ticket> createTicket(@RequestBody CreateTicketRequest request, @RequestHeader(value = "X-User-Id", required = false) String userId) {
        if (userId == null) {
            userId = "00000000-0000-0000-0000-000000000000";
        }
        
        Ticket ticket = ticketService.createTicket(request.getRawText(), request.getSubject(), UUID.fromString(userId), request.getImageBase64());
        return ResponseEntity.accepted().body(ticket);
    }
}

@Data
class CreateTicketRequest {
    private String rawText;
    private String subject;
    private String imageBase64;
}
