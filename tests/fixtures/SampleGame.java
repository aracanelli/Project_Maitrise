package com.example.game;

import java.util.List;
import java.util.logging.Logger;
import org.slf4j.LoggerFactory;

public class SampleGame {
    private static final Logger julLogger = Logger.getLogger(SampleGame.class.getName());
    private static final org.slf4j.Logger log = LoggerFactory.getLogger(SampleGame.class);
    private List<Entity> entities;

    public void update(float deltaTime) {
        log.debug("Updating game state, dt={}", deltaTime);
        for (int i = 0; i < entities.size(); i++) {
            entities.get(i).update(deltaTime);
        }
    }

    public void render() {
        julLogger.fine("Rendering frame");
        drawBackground();
        drawEntities();
    }

    public void loadResources(String path) {
        log.info("Loading resources from {}", path);
        try {
            doLoad(path);
        } catch (Exception e) {
            log.error("Failed to load resources", e);
        }
    }

    private void handleLogin(String user) {
        loginService.login(user);
    }

    public void onCollision(Entity a, Entity b) {
        log.warn("Collision detected between {} and {}", a, b);
    }

    private void drawBackground() {}
    private void drawEntities() {}
    private void doLoad(String p) {}
}
