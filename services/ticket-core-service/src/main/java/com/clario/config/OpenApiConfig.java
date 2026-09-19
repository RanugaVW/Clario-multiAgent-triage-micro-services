package com.clario.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springdoc.core.customizers.OpenApiCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** DC-015 / SUP-010: machine-readable contract, generated from the code. */
@Configuration
public class OpenApiConfig {

    static final String BEARER = "bearerAuth";

    @Bean
    public OpenAPI clarioOpenApi() {
        return new OpenAPI()
                .info(new Info()
                        .title("Clario Ticket Core Service API")
                        .version("1.0.0")
                        .description("Ticket submission and retrieval. Every endpoint requires a Supabase-issued "
                                + "JWT; identity is taken from the token's subject, never from a request header."))
                .components(new Components().addSecuritySchemes(BEARER, new SecurityScheme()
                        .type(SecurityScheme.Type.HTTP).scheme("bearer").bearerFormat("JWT")))
                .addSecurityItem(new SecurityRequirement().addList(BEARER));
    }

    /**
     * The same handlers are mapped at /api/v1/tickets and /api/tickets, so springdoc lists both.
     * Mark the unversioned one deprecated so the contract itself says which to use.
     */
    @Bean
    public OpenApiCustomizer legacyPathDeprecation() {
        return openApi -> {
            if (openApi.getPaths() == null) {
                return;
            }
            openApi.getPaths().forEach((path, item) -> {
                if (path.equals("/api/tickets") || path.startsWith("/api/tickets/")) {
                    item.readOperations().forEach(op -> {
                        op.setDeprecated(true);
                        String note = "Deprecated: use " + path.replaceFirst("^/api/", "/api/v1/") + ".";
                        op.setDescription(op.getDescription() == null ? note : note + " " + op.getDescription());
                    });
                }
            });
        };
    }
}
