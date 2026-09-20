package com.clario.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletRequestWrapper;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpServletResponseWrapper;
import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Collections;
import java.util.Enumeration;
import java.util.LinkedHashSet;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;

/**
 * DC-021 / SUP-005: every request gets a correlation ID that appears in every
 * log line it causes (via MDC), in the response header, and - at the gateway -
 * in the request forwarded downstream, so one ID follows a request across
 * services.
 *
 * An inbound ID is only trusted if it is short and made of safe characters;
 * anything else is replaced, because the value ends up in log lines and a
 * response header and must not be usable for log forging or header injection.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class CorrelationIdFilter extends OncePerRequestFilter {

    public static final String HEADER = "X-Correlation-Id";
    public static final String MDC_KEY = "correlationId";

    private static final Pattern SAFE_ID = Pattern.compile("^[A-Za-z0-9._-]{1,64}$");

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String correlationId = resolve(request.getHeader(HEADER));
        MDC.put(MDC_KEY, correlationId);
        response.setHeader(HEADER, correlationId);
        try {
            chain.doFilter(new WithCorrelationId(request, correlationId), new SingleValued(response));
        } finally {
            // Servlet threads are pooled: a leaked value would be attributed to
            // an unrelated later request.
            MDC.remove(MDC_KEY);
        }
    }

    static String resolve(String inbound) {
        return inbound != null && SAFE_ID.matcher(inbound).matches() ? inbound : UUID.randomUUID().toString();
    }

    /** Makes the (possibly generated) ID visible to whatever handles the request next, e.g. the gateway proxy. */
    private static final class WithCorrelationId extends HttpServletRequestWrapper {
        private final String correlationId;

        WithCorrelationId(HttpServletRequest request, String correlationId) {
            super(request);
            this.correlationId = correlationId;
        }

        @Override
        public String getHeader(String name) {
            return HEADER.equalsIgnoreCase(name) ? correlationId : super.getHeader(name);
        }

        @Override
        public Enumeration<String> getHeaders(String name) {
            return HEADER.equalsIgnoreCase(name)
                    ? Collections.enumeration(Collections.singletonList(correlationId))
                    : super.getHeaders(name);
        }

        @Override
        public Enumeration<String> getHeaderNames() {
            Set<String> names = new LinkedHashSet<>(Collections.list(super.getHeaderNames()));
            names.add(HEADER);
            return Collections.enumeration(names);
        }
    }

    /** A downstream service echoes the same header; keep one value instead of "id, id". */
    private static final class SingleValued extends HttpServletResponseWrapper {
        SingleValued(HttpServletResponse response) {
            super(response);
        }

        @Override
        public void addHeader(String name, String value) {
            if (HEADER.equalsIgnoreCase(name)) {
                super.setHeader(name, value);
            } else {
                super.addHeader(name, value);
            }
        }
    }
}
