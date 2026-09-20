package com.clario.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * DC-015 / DC-007: the original unversioned /api/tickets path is kept for
 * backward compatibility but flagged, on every response, as deprecated in
 * favour of /api/v1/tickets - so clients learn about the successor from the
 * API itself instead of from a changelog they may never read.
 *
 * Runs ahead of Spring Security so the signal is also present on 401/403
 * responses: a client that is failing to authenticate against the old path
 * should still be told where the supported path is.
 */
@Component
@org.springframework.core.annotation.Order(org.springframework.core.Ordered.HIGHEST_PRECEDENCE + 10)
public class LegacyApiDeprecationFilter extends OncePerRequestFilter {

    static final String LEGACY_PATH = "/api/tickets";
    static final String CURRENT_PATH = "/api/v1/tickets";

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String path = request.getRequestURI();
        if (path.equals(LEGACY_PATH) || path.startsWith(LEGACY_PATH + "/")) {
            response.setHeader("Deprecation", "true");
            response.setHeader("Link", "<" + CURRENT_PATH + path.substring(LEGACY_PATH.length()) + ">; rel=\"successor-version\"");
        }
        chain.doFilter(request, response);
    }
}
