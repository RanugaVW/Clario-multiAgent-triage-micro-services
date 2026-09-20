package com.clario;

import org.junit.jupiter.api.Test;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;
import org.yaml.snakeyaml.Yaml;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Map;
import java.util.Properties;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * REL-011: graceful shutdown is configuration, and two separate files have to agree.
 * Spring only drains for as long as its own timeouts say - but Docker sends SIGKILL
 * after stop_grace_period (10s unless set), so a generous Spring timeout with a
 * default Docker grace period is a graceful shutdown in name only.
 *
 * Reads the shipped application.properties (the test classpath's own file shadows
 * it) and the repository's docker-compose.yml.
 */
class ShutdownConfigTest {

    private static final String SERVICE = "ticket-core-service";
    private static final boolean HAS_DISPATCHER = true;

    private static Properties shipped() throws IOException {
        Resource main = Arrays.stream(new PathMatchingResourcePatternResolver().getResources("classpath*:application.properties"))
                .filter(r -> {
                    try {
                        String url = r.getURL().toString();
                        return url.contains("/classes/") && !url.contains("test-classes");
                    } catch (IOException e) {
                        return false;
                    }
                }).findFirst().orElseThrow();
        Properties props = new Properties();
        try (InputStream in = main.getInputStream()) {
            props.load(in);
        }
        return props;
    }

    /** "${NAME:20s}" or "20s" -> 20 (seconds). */
    private static long seconds(String value) {
        Matcher m = Pattern.compile("(\\d+)s?\\}?$").matcher(value.trim());
        assertThat(m.find()).as("not a seconds value: " + value).isTrue();
        return Long.parseLong(m.group(1));
    }

    @Test
    void serverShutsDownGracefully() throws IOException {
        assertThat(shipped().getProperty("server.shutdown")).isEqualTo("graceful");
        assertThat(shipped().getProperty("spring.lifecycle.timeout-per-shutdown-phase")).isNotBlank();
    }

    @Test
    void dockerIsGivenLongerThanTheTotalDrainBeforeItKills() throws IOException {
        Properties props = shipped();
        long webDrain = seconds(props.getProperty("spring.lifecycle.timeout-per-shutdown-phase"));
        long dispatchDrain = HAS_DISPATCHER ? seconds(props.getProperty("clario.dispatch.drain-timeout-seconds")) : 0;

        Path compose = Path.of("../../docker-compose.yml");
        Map<String, Object> document = new Yaml().load(Files.readString(compose));
        @SuppressWarnings("unchecked")
        Map<String, Object> service = (Map<String, Object>) ((Map<String, Object>) document.get("services")).get(SERVICE);
        assertThat(service).as(SERVICE + " must be defined in docker-compose.yml").isNotNull();
        assertThat(service).as("stop_grace_period must be set (Docker's default is 10s)").containsKey("stop_grace_period");

        long grace = seconds(String.valueOf(service.get("stop_grace_period")));
        assertThat(grace).as("stop_grace_period must exceed the drain it is meant to allow")
                .isGreaterThan(webDrain + dispatchDrain);
    }

    @Test
    void theDispatchDrainIsConfigurable_whereTheServiceHasADispatcher() throws IOException {
        if (HAS_DISPATCHER) {
            assertThat(shipped().getProperty("clario.dispatch.drain-timeout-seconds")).isNotBlank();
        }
    }
}
