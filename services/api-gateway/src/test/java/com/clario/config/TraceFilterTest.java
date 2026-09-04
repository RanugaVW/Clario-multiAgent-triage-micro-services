package com.clario.config;

import com.clario.tracing.TraceEventPublisher;
import jakarta.servlet.FilterChain;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import java.util.Map;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class TraceFilterTest {

    @Test
    void a_post_to_api_tickets_with_a_correlation_id_publishes_a_received_event() throws Exception {
        TraceEventPublisher publisher = mock(TraceEventPublisher.class);
        TraceFilter filter = new TraceFilter(publisher);

        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/tickets");
        request.addHeader("X-Trace-Correlation-Id", "c1");
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        verify(publisher).publish(eq("unknown"), eq("c1"), eq("received"), eq("done"), anyMap());
        verify(chain).doFilter(request, response);
    }

    @Test
    void a_request_without_the_correlation_id_header_never_publishes() throws Exception {
        TraceEventPublisher publisher = mock(TraceEventPublisher.class);
        TraceFilter filter = new TraceFilter(publisher);

        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/tickets");
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        verifyNoInteractions(publisher);
        verify(chain).doFilter(request, response);
    }

    @Test
    void a_request_to_a_different_path_never_publishes() throws Exception {
        TraceEventPublisher publisher = mock(TraceEventPublisher.class);
        TraceFilter filter = new TraceFilter(publisher);

        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/tickets");
        request.addHeader("X-Trace-Correlation-Id", "c1");
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);

        filter.doFilter(request, response, chain);

        verifyNoInteractions(publisher);
    }
}
