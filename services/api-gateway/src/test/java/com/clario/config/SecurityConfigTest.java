package com.clario.config;

import org.junit.jupiter.api.Test;
import org.springframework.security.oauth2.jwt.BadJwtException;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.test.util.ReflectionTestUtils;

import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * Regression test: the delegating decoder used to throw a plain JwtException
 * when both HS256 and ES256 verification failed. JwtAuthenticationProvider
 * only maps BadJwtException to a 401 (InvalidBearerTokenException) - any
 * other JwtException surfaces as an AuthenticationServiceException, which
 * Spring Security treats as a server-side failure, not "the client sent an
 * invalid token." A malformed/forged Authorization header must fail as
 * BadJwtException specifically, or every downstream 401 expectation in this
 * service (SEC-002, SEC-007, SEC-009) silently breaks.
 */
class SecurityConfigTest {

    @Test
    void jwtDecoder_onInvalidToken_throwsBadJwtException_notPlainJwtException() {
        SecurityConfig config = new SecurityConfig();
        ReflectionTestUtils.setField(config, "legacySecret", "test-only-secret-for-unit-tests-32bytes-min-0000");
        ReflectionTestUtils.setField(config, "jwksUri", "https://example.invalid/auth/v1/.well-known/jwks.json");

        JwtDecoder decoder = config.jwtDecoder();

        assertThrows(BadJwtException.class, () -> decoder.decode("not-a-real-jwt"));
    }
}
