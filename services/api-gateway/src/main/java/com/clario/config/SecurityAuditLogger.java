package com.clario.config;

import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

/**
 * FR-049 / SEC-006: authentication and authorization failures are
 * security-sensitive events and must be recorded, not just answered with a
 * 401/403. Emitted on a dedicated "security.audit" logger so operators can
 * route or alert on it separately from ordinary application logs.
 *
 * Never logs credentials: the Authorization header is deliberately not read,
 * and exception messages are truncated because some carry request detail.
 */
public final class SecurityAuditLogger {

    public static final String LOGGER_NAME = "security.audit";
    private static final Logger AUDIT = LoggerFactory.getLogger(LOGGER_NAME);
    private static final int MAX_FIELD_LENGTH = 200;

    private SecurityAuditLogger() {
    }

    public static void authenticationFailure(HttpServletRequest request, Exception cause) {
        AUDIT.warn("event=AUTHENTICATION_FAILURE method={} path={} remote={} reason=\"{}\"",
                sanitize(request.getMethod()),
                sanitize(request.getRequestURI()),
                sanitize(request.getRemoteAddr()),
                sanitize(cause == null ? "unknown" : cause.getClass().getSimpleName() + ": " + cause.getMessage()));
    }

    public static void accessDenied(HttpServletRequest request, Exception cause) {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        AUDIT.warn("event=ACCESS_DENIED method={} path={} remote={} principal={} reason=\"{}\"",
                sanitize(request.getMethod()),
                sanitize(request.getRequestURI()),
                sanitize(request.getRemoteAddr()),
                sanitize(auth == null ? "anonymous" : auth.getName()),
                sanitize(cause == null ? "unknown" : cause.getClass().getSimpleName()));
    }

    // Values here are attacker-influenced (path, exception text). Stripping
    // control characters stops a crafted request forging extra log lines.
    static String sanitize(String value) {
        if (value == null) {
            return "";
        }
        String cleaned = value.replaceAll("[\\r\\n\\t\"]", "_");
        return cleaned.length() > MAX_FIELD_LENGTH ? cleaned.substring(0, MAX_FIELD_LENGTH) + "..." : cleaned;
    }
}
