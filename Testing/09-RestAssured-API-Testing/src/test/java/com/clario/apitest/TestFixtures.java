package com.clario.apitest;

import io.restassured.path.json.JsonPath;

import java.io.File;

/**
 * Reads the fixtures.json written by setup_fixtures.py (real, disposable
 * Supabase accounts and tickets created for this run - see that script for
 * the safety model). Loaded once per JVM; run mvn test from this project's
 * root so the relative path resolves.
 */
final class TestFixtures {
    private static final JsonPath DATA = load();

    private TestFixtures() {
    }

    private static JsonPath load() {
        File file = new File("fixtures.json");
        if (!file.exists()) {
            throw new IllegalStateException(
                    "fixtures.json not found at " + file.getAbsolutePath()
                            + " - run setup_fixtures.py first (see README.md).");
        }
        return new JsonPath(file);
    }

    static String nextjsUrl() {
        return DATA.getString("nextjsUrl");
    }

    static String sidecarUrl() {
        return DATA.getString("sidecarUrl");
    }

    static String marker() {
        return DATA.getString("marker");
    }

    static String tokenA() {
        return DATA.getString("tokenA");
    }

    static String tokenB() {
        return DATA.getString("tokenB");
    }

    static String tokenStaff() {
        return DATA.getString("tokenStaff");
    }

    static String customerAId() {
        return DATA.getString("customerAId");
    }

    static String ticketResolve() {
        return DATA.getString("ticketResolve");
    }

    static String ticketFeedback() {
        return DATA.getString("ticketFeedback");
    }

    static String ticketRead() {
        return DATA.getString("ticketRead");
    }
}
