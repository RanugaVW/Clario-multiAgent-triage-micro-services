package com.clario.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.BadJwtException;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.web.SecurityFilterChain;

import javax.crypto.spec.SecretKeySpec;

/**
 * This service used to trust a client-supplied X-User-Id header with no
 * verification at all (a spoofable IDOR) for both GET and POST. It now
 * independently verifies the Supabase-issued JWT itself rather than relying
 * solely on the gateway, since this service is reachable directly on the
 * Docker network (and on its own port in local/dev runs) and must not
 * assume every caller went through the gateway's checks first.
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Value("${supabase.jwks.uri}")
    private String jwksUri;

    @Value("${jwt.legacy.secret}")
    private String legacySecret;

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf.disable())
            .cors(Customizer.withDefaults())
            .authorizeHttpRequests(authz -> authz
                .requestMatchers("/error", "/actuator/health", "/actuator/health/**").permitAll()
                .anyRequest().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt.decoder(jwtDecoder()))
            );
        return http.build();
    }

    @Bean
    public JwtDecoder jwtDecoder() {
        SecretKeySpec secretKey = new SecretKeySpec(legacySecret.getBytes(), "HmacSHA256");
        JwtDecoder hs256Decoder = NimbusJwtDecoder.withSecretKey(secretKey)
                .macAlgorithm(MacAlgorithm.HS256)
                .build();

        JwtDecoder es256Decoder = NimbusJwtDecoder.withJwkSetUri(jwksUri)
                .jwsAlgorithm(org.springframework.security.oauth2.jose.jws.SignatureAlgorithm.ES256)
                .build();

        return token -> {
            try {
                return hs256Decoder.decode(token);
            } catch (JwtException e1) {
                try {
                    return es256Decoder.decode(token);
                } catch (JwtException e2) {
                    // Must be BadJwtException specifically: JwtAuthenticationProvider maps
                    // BadJwtException to a 401 InvalidBearerTokenException, but treats any
                    // other JwtException as an AuthenticationServiceException (500-class
                    // "the auth system is broken", not "the client sent a bad token").
                    throw new BadJwtException("JWT validation failed with both HS256 and ES256: " + e2.getMessage());
                }
            }
        };
    }
}
