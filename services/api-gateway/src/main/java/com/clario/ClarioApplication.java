package com.clario;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;

@SpringBootApplication
@EnableJpaRepositories(basePackages = "com.clario.repositories")
public class ClarioApplication {

    public static void main(String[] args) {
        SpringApplication.run(ClarioApplication.class, args);
    }
}
