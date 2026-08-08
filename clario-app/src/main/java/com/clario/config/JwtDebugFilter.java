package com.clario.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Base64;

@Component
public class JwtDebugFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(JwtDebugFilter.class);

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {

        String auth = request.getHeader("Authorization");
        if (auth != null && auth.startsWith("Bearer ")) {
            String token = auth.substring(7);
            String[] parts = token.split("\\.");
            if (parts.length >= 1) {
                try {
                    byte[] headerBytes = Base64.getUrlDecoder().decode(parts[0]);
                    String header = new String(headerBytes);
                    log.warn("=== JWT HEADER: {} ===", header);
                } catch (Exception e) {
                    log.warn("=== JWT header decode failed: {} ===", e.getMessage());
                }
            }
        }
        filterChain.doFilter(request, response);
    }
}
