package com.clario.controllers;

import com.clario.entities.Ticket;
import com.clario.repositories.TicketRepository;
import com.clario.services.TicketService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/tickets")
@RequiredArgsConstructor
public class TicketController {

    private static final Logger logger = LoggerFactory.getLogger(TicketController.class);

    private final TicketService ticketService;
    private final TicketRepository ticketRepository;

    // The caller's identity comes exclusively from the signature-verified JWT
    // subject (injected by Spring Security's OAuth2 resource server filter).
    // A request with no token, or an invalid/tampered one, never reaches this
    // method at all - Spring Security rejects it with 401 first. This used to
    // trust a client-supplied X-User-Id header outright, which let any caller
    // read or create tickets as an arbitrary other user.
    @GetMapping
    public ResponseEntity<List<Ticket>> getUserTickets(@AuthenticationPrincipal Jwt jwt) {
        UUID userId = UUID.fromString(jwt.getSubject());
        return ResponseEntity.ok(ticketRepository.findByUserId(userId));
    }

    @PostMapping
    public ResponseEntity<Ticket> createTicket(@Valid @RequestBody CreateTicketRequest request, @AuthenticationPrincipal Jwt jwt) {
        UUID userId = UUID.fromString(jwt.getSubject());
        Ticket ticket = ticketService.createTicket(request.getRawText(), request.getSubject(), userId, request.getImageBase64());
        return ResponseEntity.accepted().body(ticket);
    }

    // FR-005 / SEC-008: malformed requests must be rejected with a descriptive
    // error, not the raw SQL "NOT NULL constraint" exception that used to
    // surface when rawText was blank or missing.
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleValidationErrors(MethodArgumentNotValidException ex) {
        String details = ex.getBindingResult().getFieldErrors().stream()
                .map(error -> error.getField() + ": " + error.getDefaultMessage())
                .collect(Collectors.joining("; "));
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(Map.of("error", "Validation failed", "details", details));
    }

    // REL-002: a database failure on the synchronous ticket-save path used to
    // propagate uncaught, producing Spring's generic unhandled-exception
    // response with nothing logged anywhere. It's now recorded server-side
    // and the caller gets a clear, non-leaky "try again" response instead.
    @ExceptionHandler(DataAccessException.class)
    public ResponseEntity<Map<String, Object>> handleDatabaseFailure(DataAccessException ex) {
        logger.error("Database failure while handling a ticket request", ex);
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(Map.of("error", "Ticket service is temporarily unavailable. Please try again shortly."));
    }
}

@Data
class CreateTicketRequest {
    @NotBlank(message = "rawText is required and cannot be blank")
    @Size(max = 20000, message = "rawText must not exceed 20000 characters")
    private String rawText;

    @Size(max = 500, message = "subject must not exceed 500 characters")
    private String subject;

    private String imageBase64;
}
