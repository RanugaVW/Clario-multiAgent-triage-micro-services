package com.clario.tracing;

import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class TraceEventPublisherTest {

    @Test
    void disabled_publisher_never_touches_the_rest_template() {
        RestTemplate restTemplate = mock(RestTemplate.class);
        TraceEventPublisher publisher = new TraceEventPublisher(restTemplate, false, "http://localhost:8700");

        publisher.publish("t1", "c1", "received", "done", Map.of());

        verifyNoInteractions(restTemplate);
    }

    @Test
    void enabled_publisher_posts_the_expected_body() {
        RestTemplate restTemplate = mock(RestTemplate.class);
        TraceEventPublisher publisher = new TraceEventPublisher(restTemplate, true, "http://localhost:8700");

        publisher.publish("t1", "c1", "received", "done", Map.of("k", "v"));

        verify(restTemplate, timeout(500)).postForEntity(
                eq("http://localhost:8700/trace/event"), any(), eq(Void.class));
    }

    @Test
    void a_downstream_error_never_propagates_out_of_publish() {
        RestTemplate restTemplate = mock(RestTemplate.class);
        when(restTemplate.postForEntity(any(String.class), any(), eq(Void.class)))
                .thenThrow(new RuntimeException("relay is down"));
        TraceEventPublisher publisher = new TraceEventPublisher(restTemplate, true, "http://localhost:8700");

        assertDoesNotThrow(() -> publisher.publish("t1", "c1", "received", "done", Map.of()));
    }
}
