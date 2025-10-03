import pygame
import math
import random
from constants import *
from utilities import *
from sprites import *

# --- INITIALIZATION ---
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Tank Battle - Refactored!")
clock = pygame.time.Clock()

# --- FONT INITIALIZATION ---
pygame.font.init()
try:
    debug_font = pygame.font.SysFont('Arial', 30) 
    large_font = pygame.font.SysFont('Arial', 72)
    medium_font = pygame.font.SysFont('Arial', 40)
except Exception: 
    debug_font = pygame.font.Font(None, 30) 
    large_font = pygame.font.Font(None, 72)
    medium_font = pygame.font.Font(None, 40)

# --- SOUND INITIALIZATION ---
pygame.mixer.init()
fire_sound = None
explosion_sound = None
hit_sound = None

class DummySound:
    """Class to prevent crashes if sound files are missing."""
    def play(self): pass
    def set_volume(self, vol): pass

try:
    # IMPORTANT: You must create a 'sounds' folder and add sound files for this to work.
    fire_sound = pygame.mixer.Sound(SOUND_FIRE_PATH)
    explosion_sound = pygame.mixer.Sound(SOUND_EXPLOSION_PATH)
    hit_sound = pygame.mixer.Sound(SOUND_HIT_PATH)
    
    fire_sound.set_volume(SOUND_VOLUME)
    explosion_sound.set_volume(SOUND_VOLUME)
    hit_sound.set_volume(SOUND_VOLUME * 0.7)
    print("Sounds loaded successfully.")
    
except pygame.error as e:
    print(f"Warning: Could not load sound files. Error: {e}")
    fire_sound = DummySound()
    explosion_sound = DummySound()
    hit_sound = DummySound()

# --- GLOBAL GAME STATE VARIABLES ---
terrain_features = []
generated_chunks = set()
bullets = pygame.sprite.Group() 
tanks = pygame.sprite.Group() 
player_tank = None # Will be initialized in initialize_game
game_over = False
game_result = ""
restart_button_rect = None # Stores the rect of the restart button for click detection

# ----------------------------------------------------
# --- GAME SETUP FUNCTIONS ---
# ----------------------------------------------------
def initialize_game():
    """Initializes all game objects and world state."""
    global terrain_features, generated_chunks, bullets, tanks, player_tank
    
    # Reset groups and lists
    terrain_features = []
    generated_chunks = set()
    bullets.empty()
    tanks.empty()
    
    # Generate initial terrain (Center chunks)
    for y in range(-1, 2):
        for x in range(-1, 2):
            terrain_features.extend(generate_chunk(x, y))
            generated_chunks.add((x, y))

    # Initialize Player Tank (Pass sound objects)
    start_x, start_y = find_safe_spawn_position(terrain_features, min_dist=150, spawn_area_size=1)
    new_player_tank = PlayerTank(start_x, start_y, fire_sound, explosion_sound)
    tanks.add(new_player_tank)

    # Initialize Other Tanks (Pass sound objects)
    NUM_FRIENDLIES = 2
    NUM_ENEMIES = 3

    for _ in range(NUM_FRIENDLIES):
        x, y = find_safe_spawn_position(terrain_features, min_dist=150, spawn_area_size=4)
        friendly = Tank(x, y, 'Friendly', fire_sound, explosion_sound) 
        tanks.add(friendly)

    for _ in range(NUM_ENEMIES):
        x, y = find_safe_spawn_position(terrain_features, min_dist=150, spawn_area_size=4)
        enemy = EnemyTank(x, y, fire_sound, explosion_sound) 
        tanks.add(enemy)
        
    return new_player_tank

def reset_game():
    """Resets the game state and reinitializes game objects."""
    global game_over, game_result, player_tank
    
    # Reinitialize all game objects
    player_tank = initialize_game()
    
    # Reset game state flags
    game_over = False
    game_result = ""

# Initial game setup
player_tank = initialize_game()

# ----------------------------------------------------
# --- GAME LOOP ---
# ----------------------------------------------------
running = True
while running:
    
    # ------------------ EVENT HANDLING ------------------
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        
        if not game_over:
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    # Player fire() is called here
                    player_tank.fire(bullets) 
        elif game_over:
            # Check for restart button click
            if event.type == pygame.MOUSEBUTTONDOWN and restart_button_rect:
                if restart_button_rect.collidepoint(event.pos):
                    print("Restarting game...")
                    reset_game()
                    # Continue loop with new game state
                    continue 

    keys = pygame.key.get_pressed()
    mouse_pos = pygame.mouse.get_pos()
    
    # --- Listener Position (Player's World Coordinates) ---
    listener_x = player_tank.x
    listener_y = player_tank.y
    
    # ------------------ UPDATE LOGIC ------------------
    if not game_over:
        
        # Player Update
        player_tank.update(keys, mouse_pos, terrain_features)
        
        enemies_left = 0
        for tank in tanks:
            if isinstance(tank, EnemyTank):
                # Enemy update requires the bullets group to fire
                tank.update(player_tank, terrain_features, bullets) 
                if tank.is_alive:
                    enemies_left += 1
            elif tank != player_tank and tank.is_alive:
                # --- FRIENDLY TANK AI ---
                
                # 1. Target Acquisition (Find the nearest enemy)
                nearest_enemy = None
                min_dist_sq = float('inf')
                
                for enemy in tanks:
                    # Only consider active enemies
                    if enemy.allegiance == 'Enemy' and enemy.is_alive:
                        dist_sq = (tank.x - enemy.x)**2 + (tank.y - enemy.y)**2
                        if dist_sq < min_dist_sq:
                            min_dist_sq = dist_sq
                            nearest_enemy = enemy
                            
                # 2. Turret Aiming and Firing
                friendly_keys = {pygame.K_w: False, pygame.K_r: False, pygame.K_a: False, pygame.K_s: False}
                
                if nearest_enemy:
                    # Aim at the enemy
                    dx = nearest_enemy.x - tank.x
                    dy = nearest_enemy.y - tank.y
                    target_angle = math.degrees(math.atan2(-dy, dx))
                    tank.rotate_turret(target_angle)
                    
                    # Fire if target is within range and cooldown is 0
                    if min_dist_sq <= MAX_BULLET_RANGE**2 and tank.fire_cooldown == 0:
                        # Fire requires the bullets group and listener position (player's coordinates)
                        tank.fire(bullets, player_tank.x, player_tank.y)
                        
                    # Slow movement: Advance if the enemy is far, stop if they are close
                    if min_dist_sq > (MAX_BULLET_RANGE * 0.75)**2:
                         friendly_keys[pygame.K_w] = True
                    # If target is too close, reverse slightly (optional evasive maneuver)
                    # elif min_dist_sq < (TANK_WIDTH * 5)**2:
                    #     friendly_keys[pygame.K_r] = True 

                else:
                    # If no enemy, keep the tank moving forward slowly
                    friendly_keys[pygame.K_w] = True
                
                # 3. Movement
                tank.update_movement(friendly_keys, is_player=False, features=terrain_features)
                 
                # 4. Cooldown
                if tank.fire_cooldown > 0:
                    tank.fire_cooldown -= 1


        # --- CAMERA OFFSET CALCULATION ---
        ideal_offset_x = SCREEN_WIDTH // 2 - listener_x
        ideal_offset_y = SCREEN_HEIGHT // 2 - listener_y
        
        # Clamp camera to world boundaries
        max_offset_x = -WORLD_MIN_X 
        max_offset_y = -WORLD_MIN_Y 
        min_offset_x = SCREEN_WIDTH - WORLD_MAX_X 
        min_offset_y = SCREEN_HEIGHT - WORLD_MAX_Y 
        
        camera_offset_x = max(min_offset_x, min(max_offset_x, ideal_offset_x))
        camera_offset_y = max(min_offset_y, min(max_offset_y, ideal_offset_y))
        
        # Update bullets.
        bullets.update(camera_offset_x, camera_offset_y, terrain_features) 

        # --- COMBAT: BULLET COLLISION AND DAMAGE ---
        for bullet in bullets:
            active_tanks = [t for t in tanks if t.is_alive] 
            hit_tanks = pygame.sprite.spritecollide(bullet, active_tanks, False) 
            
            for tank_hit in hit_tanks:
                if tank_hit.rect.collidepoint(bullet.rect.center):
                    # TANK DAMAGE: Explosion sound volume is now calculated inside take_damage()
                    tank_hit.take_damage(BULLET_DAMAGE, listener_x, listener_y) 
                    bullet.kill() 
                    
                    # HIT SOUND: Volume must be calculated here since the sound object belongs to main.py
                    distance = math.hypot(bullet.x - listener_x, bullet.y - listener_y)
                    volume_ratio = 1.0 - (distance / MAX_SOUND_DISTANCE)
                    # Apply a base factor (0.7) and clamp the volume
                    final_volume = max(0.0, min(1.0, volume_ratio)) * SOUND_VOLUME * 0.7 
                    
                    hit_sound.set_volume(final_volume)
                    hit_sound.play() 
                    break
                    
        # --- GAME STATE CHECK ---
        if player_tank.is_wreck and not game_over:
            game_over = True
            game_result = "DEFEAT! Your tank was destroyed."
        
        enemies_left = sum(1 for t in tanks if t.allegiance == 'Enemy' and t.is_alive)
        
        if enemies_left == 0 and sum(1 for tank in tanks if tank.allegiance == 'Enemy') > 0 and not game_over:
            game_over = True
            game_result = "VICTORY! All enemy tanks destroyed."


    # --- DYNAMIC CHUNK GENERATION ---
    if player_tank.is_alive:
        player_chunk_x = int(listener_x) // CHUNK_SIZE
        player_chunk_y = int(listener_y) // CHUNK_SIZE
    else: 
        player_chunk_x = int(SCREEN_WIDTH/2 - camera_offset_x) // CHUNK_SIZE
        player_chunk_y = int(SCREEN_HEIGHT/2 - camera_offset_y) // CHUNK_SIZE
        
    for y in range(player_chunk_y - 1, player_chunk_y + 2):
        for x in range(player_chunk_x - 1, player_chunk_x + 2):
            if (x, y) not in generated_chunks:
                terrain_features.extend(generate_chunk(x, y))
                generated_chunks.add((x, y))

    # Clean up far-off terrain features
    terrain_features = [f for f in terrain_features if abs(f.x - player_tank.x) < WORLD_SIZE_X and abs(f.y - player_tank.y) < WORLD_SIZE_Y]

    # ------------------ DRAWING ------------------
    screen.fill(GREEN)
    
    # Draw terrain features
    for feature in terrain_features:
        moved_feature = feature.move(camera_offset_x, camera_offset_y)
        pygame.draw.rect(screen, BROWN, moved_feature)
    
    # Draw world boundaries
    boundary_rect_screen = pygame.Rect(
        WORLD_MIN_X + camera_offset_x, 
        WORLD_MIN_Y + camera_offset_y, 
        WORLD_SIZE_X, 
        WORLD_SIZE_Y
    )
    line_thickness = 5
    pygame.draw.line(screen, BOUNDARY_COLOR, boundary_rect_screen.topleft, boundary_rect_screen.topright, line_thickness)
    pygame.draw.line(screen, BOUNDARY_COLOR, boundary_rect_screen.bottomleft, boundary_rect_screen.bottomright, line_thickness)
    pygame.draw.line(screen, BOUNDARY_COLOR, boundary_rect_screen.topleft, boundary_rect_screen.bottomleft, line_thickness)
    pygame.draw.line(screen, BOUNDARY_COLOR, boundary_rect_screen.topright, boundary_rect_screen.bottomright, line_thickness)


    # Draw bullets
    bullets.draw(screen)

    # Draw all tanks (Wrecks first, then live tanks)
    for tank in tanks:
        if tank.is_wreck:
             tank.draw(screen, camera_offset_x, camera_offset_y)
    for tank in tanks:
        if tank.is_alive:
             tank.draw(screen, camera_offset_x, camera_offset_y)
    
    # Draw debug/info text
    real_fps = clock.get_fps() 
    
    mode_text = f"HP: {player_tank.health} | Enemies Left: {enemies_left}"
    cooldown_text = f"Ready in: {max(0, player_tank.fire_cooldown) / FPS:.2f}s"
    angle_speed_text = f"Angle: {player_tank.angle:.2f}° | Speed: {player_tank.speed:.2f}"
    fps_text = f"FPS: {real_fps:.2f}"
    
    if 'debug_font' in locals() and debug_font:
        text_surface_mode = debug_font.render(mode_text, True, BLACK)
        text_surface_cooldown = debug_font.render(cooldown_text, True, RED if player_tank.fire_cooldown > 0 else PLAYER_COLOR)
        text_surface_angle_speed = debug_font.render(angle_speed_text, True, BLACK)
        text_surface_fps = debug_font.render(fps_text, True, BLACK)
    
        screen.blit(text_surface_mode, (10, 10))
        screen.blit(text_surface_cooldown, (10, 40))
        screen.blit(text_surface_angle_speed, (10, 70))
        screen.blit(text_surface_fps, (10, 100))
    
    # --- GAME OVER SCREEN & RESTART BUTTON ---
    if game_over:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180)) 
        screen.blit(overlay, (0, 0))
        
        # 1. Draw Result Text
        color = YELLOW if game_result.startswith("VICTORY") else RED
        
        if 'large_font' in locals() and large_font:
            result_text = large_font.render(game_result, True, color)
            result_rect = result_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50))
            screen.blit(result_text, result_rect)

        # 2. Draw Restart Button
        restart_text = "Restart Game"
        restart_surface = medium_font.render(restart_text, True, WHITE)
        
        # Create the button rectangle (with padding)
        padding_x, padding_y = 30, 15
        restart_rect = restart_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 80))
        
        button_rect = pygame.Rect(
            restart_rect.left - padding_x, 
            restart_rect.top - padding_y, 
            restart_rect.width + padding_x * 2, 
            restart_rect.height + padding_y * 2
        )
        
        # Store the rect for click detection
        restart_button_rect = button_rect 
        
        # Draw button background
        pygame.draw.rect(screen, PLAYER_COLOR, button_rect, border_radius=10)
        
        # Draw text on top
        screen.blit(restart_surface, restart_rect.topleft)

    else:
        # Reset button rect when game is active to prevent accidental clicks
        restart_button_rect = None

    # Update the entire screen
    pygame.display.flip()
    
    # Limit FPS
    clock.tick(FPS)

pygame.quit()
