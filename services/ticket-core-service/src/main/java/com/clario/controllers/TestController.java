package com.clario.controllers;
import org.springframework.web.bind.annotation.*;
@RestController
@RequestMapping("/api/test")
public class TestController {
    @PostMapping
    public String test() { return "OK"; }
}
