import pygame
import random
from constants import *

# --- UTILITY DRAWING FUNCTIONS ---

def draw_button(surface, text, font, center_x, center_y, text_color, button_color, padding_x=30, padding_y=15, border_radius=10):
    """
    Renders a button with text centered at the specified coordinates.
    Returns the final pygame.Rect object of the button's background.
    """
    
    # Render the text
    text_surface = font.render(text, True, text_color)
    text_rect = text_surface.get_rect(center=(center_x, center_y))
    
    # Create the button background rectangle (with padding)
    button_rect = pygame.Rect(
        text_rect.left - padding_x, 
        text_rect.top - padding_y, 
        text_rect.width + padding_x * 2, 
        text_rect.height + padding_y * 2
    )
    
    # Draw button background
    pygame.draw.rect(surface, button_color, button_rect, border_radius=border_radius)
    
    # Draw text on top
    surface.blit(text_surface, text_rect.topleft)
    
    return button_rect

def generate_chunk(chunk_x, chunk_y):
    """
    Generates terrain features (obstacles) for a specific chunk area.
    Features are represented as pygame.Rect objects in world coordinates.
    """
    features = []
    
    # Calculate world boundaries for this chunk
    start_x = chunk_x * CHUNK_SIZE
    start_y = chunk_y * CHUNK_SIZE
    end_x = start_x + CHUNK_SIZE
    end_y = start_y + CHUNK_SIZE
    
    # Iterate through potential feature locations
    for x in range(start_x, end_x, TANK_WIDTH // 2):
        for y in range(start_y, end_y, TANK_HEIGHT // 2):
            
            # Use random density to determine if an obstacle should be placed
            if random.random() < FEATURE_DENSITY:
                # FIX: Convert the results of float multiplication to integers 
                # before passing them to random.randint()
                w = random.randint(int(TANK_WIDTH * 0.5), int(TANK_WIDTH * 1.5))
                h = random.randint(int(TANK_HEIGHT * 0.5), int(TANK_HEIGHT * 1.5))
                
                # Create the rect in world coordinates
                feature_rect = pygame.Rect(x - w // 2, y - h // 2, w, h)
                
                # Check that the feature is within the overall world bounds
                if (feature_rect.right > WORLD_MAX_X or feature_rect.left < WORLD_MIN_X or
                    feature_rect.bottom > WORLD_MAX_Y or feature_rect.top < WORLD_MIN_Y):
                    continue
                    
                features.append(feature_rect)
                
    return features

def find_safe_spawn_position(features, min_dist, spawn_area_size):
    """
    Finds a random world position that is at least min_dist away from any feature.
    Restricts spawning to the central spawn_area_size chunks.
    """
    
    # Determine the spawning bounding box
    half_size = (spawn_area_size * CHUNK_SIZE) // 2
    
    attempts = 0
    max_attempts = 1000
    
    while attempts < max_attempts:
        
        # Select a random position within the central spawn area
        x = random.uniform(-half_size, half_size)
        y = random.uniform(-half_size, half_size)
        
        # Check against the world bounds
        if (x < WORLD_MIN_X or x > WORLD_MAX_X or 
            y < WORLD_MIN_Y or y > WORLD_MAX_Y):
            attempts += 1
            continue
            
        # Create a temporary tank collision box (slightly larger for safety)
        tank_rect = pygame.Rect(x - TANK_WIDTH // 2, y - TANK_HEIGHT // 2, TANK_WIDTH, TANK_HEIGHT)
        
        # Check for collision with existing features
        is_safe = True
        for feature in features:
            if tank_rect.colliderect(feature):
                is_safe = False
                break
        
        if is_safe:
            return x, y
        
        attempts += 1
        
    # Fallback to a central position if a safe spot cannot be found quickly
    return 0, 0
