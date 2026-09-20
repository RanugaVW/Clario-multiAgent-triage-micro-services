package com.clario;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

// @EnableJpaRepositories lives in com.clario.config.JpaConfig, not here.
// Annotations declared directly on the @SpringBootApplication class are
// always pulled into every @WebMvcTest/@DataJpaTest slice context (slice
// tests can only exclude auto-configuration, not annotations on the root
// config class itself) - keeping it on this class made the JPA repository
// infrastructure unavoidable even in a pure web-layer slice test.
@SpringBootApplication
public class ClarioApplication {

    public static void main(String[] args) {
        SpringApplication.run(ClarioApplication.class, args);
    }
}
