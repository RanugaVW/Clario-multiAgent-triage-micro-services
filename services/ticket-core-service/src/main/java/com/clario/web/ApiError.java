package com.clario.web;

import com.fasterxml.jackson.annotation.JsonInclude;
import io.swagger.v3.oas.annotations.media.Schema;

/**
 * The single error shape every failure response uses. Handlers return this
 * type and the OpenAPI spec references it, so the documented contract and the
 * actual behaviour cannot drift apart.
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
@Schema(name = "ApiError", description = "Error body returned for every failed request.")
public record ApiError(
        @Schema(description = "Human-readable summary. Never contains internal detail.",
                example = "Validation failed")
        String error,
        @Schema(description = "Identifier that also appears on the server's log lines for this request. Quote it to support.",
                example = "7d1c2f0e-5b3a-4c39-9a52-0f1f0c8f6c11")
        String reference,
        @Schema(description = "Field-level explanation; present for validation failures only.",
                example = "rawText: rawText is required and cannot be blank")
        String details) {

    static ApiError of(String error, String reference) {
        return new ApiError(error, reference, null);
    }
}
