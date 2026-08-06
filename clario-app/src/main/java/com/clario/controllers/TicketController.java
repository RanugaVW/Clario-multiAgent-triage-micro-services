package com.clario.controllers;

import com.clario.entities.Ticket;
import com.clario.repositories.TicketRepository;
import com.clario.services.TicketService;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
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
    public ResponseEntity<List<Ticket>> getUserTickets(@AuthenticationPrincipal Jwt jwt) {
        UUID userId = UUID.fromString(jwt.getSubject());
        return ResponseEntity.ok(ticketRepository.findByUserId(userId));
    }

    @PostMapping
    public ResponseEntity<Ticket> createTicket(@RequestBody CreateTicketRequest request, @AuthenticationPrincipal Jwt jwt) {
        // Extract the user UUID from the Supabase JWT 'sub' claim
        UUID userId = UUID.fromString(jwt.getSubject());
        
        Ticket ticket = ticketService.createTicket(request.getRawText(), request.getSubject(), userId);
        return ResponseEntity.accepted().body(ticket);
    }
}

@Data
class CreateTicketRequest {
    private String rawText;
    private String subject;
}
