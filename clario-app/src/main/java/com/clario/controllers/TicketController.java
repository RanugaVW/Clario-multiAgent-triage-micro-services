package com.clario.controllers;

import com.clario.entities.Ticket;
import com.clario.services.TicketService;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/tickets")
@RequiredArgsConstructor
public class TicketController {

    private final TicketService ticketService;

    @PostMapping
    public ResponseEntity<Ticket> createTicket(@RequestBody CreateTicketRequest request) {
        UUID userId = request.getUserId() != null ? UUID.fromString(request.getUserId()) : null;
        Ticket ticket = ticketService.createTicket(request.getRawText(), request.getSubject(), userId);
        return ResponseEntity.accepted().body(ticket);
    }
}

@Data
class CreateTicketRequest {
    private String rawText;
    private String subject;
    private String userId;
}
