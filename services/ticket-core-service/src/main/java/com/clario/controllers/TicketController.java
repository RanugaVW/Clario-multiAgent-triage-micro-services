package com.clario.controllers;

import com.clario.entities.Ticket;
import com.clario.repositories.TicketRepository;
import com.clario.services.TicketService;
import com.clario.web.ApiError;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@Tag(name = "Tickets", description = "Submit and retrieve the caller's own support tickets.")
// /api/v1/tickets is the versioned contract. /api/tickets is the original,
// unversioned path, kept as a deprecated alias so existing clients keep working
// (see LegacyApiDeprecationFilter); breaking changes go in a new version.
@RequestMapping({"/api/v1/tickets", "/api/tickets"})
@RequiredArgsConstructor
public class TicketController {

    private final TicketService ticketService;
    private final TicketRepository ticketRepository;

    // The caller's identity comes exclusively from the signature-verified JWT
    // subject (injected by Spring Security's OAuth2 resource server filter).
    // A request with no token, or an invalid/tampered one, never reaches this
    // method at all - Spring Security rejects it with 401 first. This used to
    // trust a client-supplied X-User-Id header outright, which let any caller
    // read or create tickets as an arbitrary other user.
    @Operation(summary = "List the caller's tickets",
            description = "Returns only tickets owned by the authenticated user (JWT subject).")
    @ApiResponses({
            @ApiResponse(responseCode = "200", description = "The caller's tickets (possibly empty)."),
            @ApiResponse(responseCode = "401", description = "Missing, malformed, expired or forged token.", content = @Content),
            @ApiResponse(responseCode = "503", description = "Database temporarily unavailable.",
                    content = @Content(schema = @Schema(implementation = ApiError.class)))
    })
    @GetMapping
    public ResponseEntity<List<Ticket>> getUserTickets(@AuthenticationPrincipal Jwt jwt) {
        UUID userId = UUID.fromString(jwt.getSubject());
        return ResponseEntity.ok(ticketRepository.findByUserId(userId));
    }

    @Operation(summary = "Submit a support ticket",
            description = "Persists the ticket and queues it for AI triage asynchronously - 202 means accepted, "
                    + "not resolved.")
    @ApiResponses({
            @ApiResponse(responseCode = "202", description = "Ticket accepted for processing."),
            @ApiResponse(responseCode = "400", description = "Validation failed (e.g. blank rawText).",
                    content = @Content(schema = @Schema(implementation = ApiError.class))),
            @ApiResponse(responseCode = "401", description = "Missing, malformed, expired or forged token.", content = @Content),
            @ApiResponse(responseCode = "503", description = "Database temporarily unavailable.",
                    content = @Content(schema = @Schema(implementation = ApiError.class)))
    })
    @PostMapping
    public ResponseEntity<Ticket> createTicket(
            @Valid @RequestBody CreateTicketRequest request,
            @AuthenticationPrincipal Jwt jwt,
            @RequestHeader(value = "X-Trace-Correlation-Id", required = false) String correlationId) {
        UUID userId = UUID.fromString(jwt.getSubject());
        Ticket ticket = ticketService.createTicket(request.getRawText(), request.getSubject(), userId, request.getImageBase64(), correlationId);
        return ResponseEntity.accepted().body(ticket);
    }
}

@Data
class CreateTicketRequest {
    @Schema(description = "The customer's message. Must contain at least one non-whitespace character.",
            maxLength = 20000)
    @NotBlank(message = "rawText is required and cannot be blank")
    @Size(max = 20000, message = "rawText must not exceed 20000 characters")
    private String rawText;

    @Schema(description = "Optional short subject line.", maxLength = 500)
    @Size(max = 500, message = "subject must not exceed 500 characters")
    private String subject;

    @Schema(description = "Optional base64-encoded image attachment (no data: prefix); processed by OCR.")
    private String imageBase64;
}

