package com.clario.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import javax.crypto.spec.SecretKeySpec;
import java.util.Arrays;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf.disable())
            .cors(Customizer.withDefaults())
            .authorizeHttpRequests(authz -> authz
                .requestMatchers("/actuator/**", "/error").permitAll()
                .anyRequest().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt.decoder(jwtDecoder()))
            );
        return http.build();
    }

    @Value("${supabase.jwks.uri}")
    private String jwksUri;

    @Value("${jwt.legacy.secret}")
    private String legacySecret;

    @Value("${clario.cors.allowed-origins:http://localhost:3000}")
    private String allowedOrigins;

    @Bean
    public JwtDecoder jwtDecoder() {
        // HS256 decoder using the legacy Supabase shared secret
        SecretKeySpec secretKey = new SecretKeySpec(legacySecret.getBytes(), "HmacSHA256");
        JwtDecoder hs256Decoder = NimbusJwtDecoder.withSecretKey(secretKey)
                .macAlgorithm(MacAlgorithm.HS256)
                .build();

        // ES256 decoder using Supabase JWKS (new signing key) - must explicitly declare ES256
        JwtDecoder es256Decoder = NimbusJwtDecoder.withJwkSetUri(jwksUri)
                .jwsAlgorithm(org.springframework.security.oauth2.jose.jws.SignatureAlgorithm.ES256)
                .build();

        // Delegating decoder: try HS256 first (legacy), fall back to ES256 (new)
        return token -> {
            try {
                return hs256Decoder.decode(token);
            } catch (JwtException e1) {
                try {
                    return es256Decoder.decode(token);
                } catch (JwtException e2) {
                    throw new JwtException("JWT validation failed with both HS256 and ES256: " + e2.getMessage());
                }
            }
        };
    }

    @Bean
    CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();
        configuration.setAllowedOrigins(Arrays.asList(allowedOrigins.split(",")));
        configuration.setAllowedMethods(Arrays.asList("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        configuration.setAllowedHeaders(Arrays.asList("Authorization", "Cache-Control", "Content-Type", "apikey", "X-Trace-Correlation-Id"));
        configuration.setAllowCredentials(true);
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }
}
