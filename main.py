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
    small_font = pygame.font.SysFont('Arial', 24) # New font for options
except Exception: 
    debug_font = pygame.font.Font(None, 30) 
    large_font = pygame.font.Font(None, 72)
    medium_font = pygame.font.Font(None, 40)
    small_font = pygame.font.Font(None, 24) # New font for options

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

# NEW GAME STATE VARIABLES
game_state = STATE_GAMEPLAY
# Rects for options menu buttons
options_button_rects = {}
is_rebinding = False
rebinding_key_name = ""


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
    global game_over, game_result, player_tank, game_state
    
    # Preserve player tank's control settings across resets
    old_drive_system = player_tank.drive_system if player_tank else DEFAULT_DRIVE_SYSTEM
    old_control_keys = player_tank.control_keys if player_tank else {}

    # Reinitialize all game objects
    player_tank = initialize_game()
    
    # Restore player tank's control settings
    player_tank.drive_system = old_drive_system
    if old_control_keys:
        player_tank.control_keys = old_control_keys

    # Reset game state flags
    game_over = False
    game_result = ""
    game_state = STATE_GAMEPLAY

# Initial game setup
player_tank = initialize_game()

# ----------------------------------------------------
# --- UI DRAWING FUNCTIONS ---
# ----------------------------------------------------
def draw_button(surface, text, font, center_x, center_y, color, back_color):
    """Utility function to draw a clickable button."""
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect(center=(center_x, center_y))
    
    padding_x, padding_y = 20, 10
    button_rect = pygame.Rect(
        text_rect.left - padding_x, 
        text_rect.top - padding_y, 
        text_rect.width + padding_x * 2, 
        text_rect.height + padding_y * 2
    )
    
    pygame.draw.rect(surface, back_color, button_rect, border_radius=5)
    surface.blit(text_surface, text_rect.topleft)
    return button_rect

def draw_pause_menu():
    """Draws the transparent pause overlay and menu options."""
    global options_button_rects
    options_button_rects = {} # Clear rects for current menu
    
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180)) 
    screen.blit(overlay, (0, 0))
    
    if 'large_font' in locals() and large_font:
        pause_text = large_font.render("PAUSED", True, WHITE)
        pause_rect = pause_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 100))
        screen.blit(pause_text, pause_rect)

    center_x = SCREEN_WIDTH // 2
    y_start = SCREEN_HEIGHT // 2
    
    # Resume Button
    resume_rect = draw_button(screen, "Resume (P)", medium_font, center_x, y_start, WHITE, PLAYER_COLOR)
    options_button_rects['resume'] = resume_rect # <<< Store for click detection
    
    # Options Button
    options_rect = draw_button(screen, "Options (O)", medium_font, center_x, y_start + 70, WHITE, DARK_GRAY)
    
    # Store for click detection
    options_button_rects['options'] = options_rect

def get_key_name(key_code):
    """Converts a pygame key code into a human-readable string."""
    try:
        return pygame.key.name(key_code).upper()
    except:
        return f"Key {key_code}"

def draw_options_menu():
    """Draws the options screen for drive system and keybinding."""
    global options_button_rects, is_rebinding, rebinding_key_name
    
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 220)) 
    screen.blit(overlay, (0, 0))

    if 'large_font' in locals() and large_font:
        title_text = large_font.render("Options", True, WHITE)
        title_rect = title_text.get_rect(center=(SCREEN_WIDTH // 2, 100))
        screen.blit(title_text, title_rect)

    center_x = SCREEN_WIDTH // 2
    y_current = 200
    options_button_rects = {} # Clear for new button placements

    # --- Drive System Selection ---
    
    # Render the Drive System label using medium font
    drive_text = medium_font.render("Drive System:", True, WHITE)
    screen.blit(drive_text, (center_x - 300, y_current))
    
    # 1. Standard Drive Button
    text = f"Standard (WASD)"
    color = YELLOW if player_tank.drive_system == DRIVE_SYSTEM_STANDARD else WHITE
    back_color = PLAYER_COLOR if player_tank.drive_system == DRIVE_SYSTEM_STANDARD else DARK_GRAY
    rect = draw_button(screen, text, small_font, center_x, y_current + 5, color, back_color)
    options_button_rects['drive_standard'] = rect
    
    # Move to the next line
    y_current += 70 
    
    # 2. Independent Track Drive Button
    text = f"Independent Track (Arrows)"
    color = YELLOW if player_tank.drive_system == DRIVE_SYSTEM_INDEPENDENT else WHITE
    back_color = PLAYER_COLOR if player_tank.drive_system == DRIVE_SYSTEM_INDEPENDENT else DARK_GRAY
    rect = draw_button(screen, text, small_font, center_x, y_current + 5, color, back_color)
    options_button_rects['drive_independent'] = rect # <<< THIS IS THE BUTTON

    y_current += 70 # Advance y_current again for the Key Rebinding section
    
    # ... (rest of the function for Key Rebinding continues)

    # --- Key Rebinding Section ---
    if is_rebinding:
        rebind_text = large_font.render(f"Press new key for: {rebinding_key_name}", True, RED)
        rebind_rect = rebind_text.get_rect(center=(SCREEN_WIDTH // 2, y_current + 50))
        screen.blit(rebind_text, rebind_rect)
        y_current += 150
    else:
        # Drawing the keybinding options
        key_map = player_tank.control_keys[player_tank.drive_system]
        keys_to_bind = list(key_map.keys())
        key_names = {
            'f': "Forward", 'r': "Reverse", 'l': "Turn Left", 's': "Turn Right",
            'lf': "Left Track Forward", 'lr': "Left Track Reverse", 
            'rf': "Right Track Forward", 'rr': "Right Track Reverse"
        }
        
        col_start = SCREEN_WIDTH // 4
        
        for i, key_id in enumerate(keys_to_bind):
            row = i // 2
            col = i % 2
            
            x = col_start + col * (SCREEN_WIDTH // 2)
            y = y_current + row * 60
            
            key_code = key_map[key_id]
            key_text = get_key_name(key_code)
            
            label = small_font.render(f"{key_names[key_id]}:", True, WHITE)
            screen.blit(label, (x - 100, y))
            
            # Key Button
            text = key_text
            back_color = PLAYER_COLOR
            rect = draw_button(screen, text, small_font, x + 150, y, WHITE, back_color)
            options_button_rects[f'bind_{key_id}'] = rect
            
        y_current += (len(keys_to_bind) // 2) * 60 + 50
        
    # --- Back Button ---
    back_rect = draw_button(screen, "Back (P/O/ESC)", medium_font, center_x, SCREEN_HEIGHT - 100, WHITE, RED)
    options_button_rects['back'] = back_rect

# ----------------------------------------------------
# --- GAME LOOP ---
# ----------------------------------------------------
running = True
while running:
    
    # ------------------ EVENT HANDLING ------------------
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        
        # --- Universal Controls: Pause/Options/Escape ---
        if event.type == pygame.KEYDOWN:
            if event.key == KEY_PAUSE:
                if game_state == STATE_GAMEPLAY:
                    if not game_over: game_state = STATE_PAUSED
                elif game_state == STATE_PAUSED:
                    game_state = STATE_GAMEPLAY
                elif game_state == STATE_OPTIONS:
                    # 'P' key acts as 'Back' from options
                    game_state = STATE_PAUSED
            elif event.key == KEY_OPTIONS or event.key == pygame.K_ESCAPE:
                if game_state == STATE_PAUSED:
                    game_state = STATE_OPTIONS
                elif game_state == STATE_OPTIONS:
                    # 'O' or 'ESC' acts as 'Back' from options
                    game_state = STATE_PAUSED
                    
            # --- Key Rebinding Capture ---
            if game_state == STATE_OPTIONS and is_rebinding and event.key not in [KEY_PAUSE, KEY_OPTIONS, pygame.K_ESCAPE, pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_LCTRL, pygame.K_RCTRL, pygame.K_LALT, pygame.K_RALT]:
                # Assign the new key
                current_map = player_tank.control_keys[player_tank.drive_system]
                # Find the key_id (e.g., 'f', 'lf') from the rebinding_key_name
                key_name_to_id = {
                    "Forward": 'f', "Reverse": 'r', "Turn Left": 'l', "Turn Right": 's',
                    "Left Track Forward": 'lf', "Left Track Reverse": 'lr', 
                    "Right Track Forward": 'rf', "Right Track Reverse": 'rr'
                }
                key_id = key_name_to_id.get(rebinding_key_name)
                
                if key_id:
                    current_map[key_id] = event.key
                
                is_rebinding = False
                rebinding_key_name = ""


        # --- Mouse Clicks ---
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            
            if game_state == STATE_GAMEPLAY and not game_over:
                # Player fire() is called here
                player_tank.fire(bullets)
                
            elif game_over and restart_button_rect and restart_button_rect.collidepoint(mouse_pos):
                print("Restarting game...")
                reset_game()
                continue
                
            elif game_state == STATE_PAUSED:
                if 'resume' in options_button_rects and options_button_rects['resume'].collidepoint(mouse_pos):
                    game_state = STATE_GAMEPLAY
                elif 'options' in options_button_rects and options_button_rects['options'].collidepoint(mouse_pos):
                    game_state = STATE_OPTIONS
                    
            elif game_state == STATE_OPTIONS:
                
                # Back button
                if 'back' in options_button_rects and options_button_rects['back'].collidepoint(mouse_pos):
                    game_state = STATE_PAUSED
                    
                # Drive System Selection
                elif 'drive_standard' in options_button_rects and options_button_rects['drive_standard'].collidepoint(mouse_pos):
                    player_tank.drive_system = DRIVE_SYSTEM_STANDARD
                elif 'drive_independent' in options_button_rects and options_button_rects['drive_independent'].collidepoint(mouse_pos):
                    player_tank.drive_system = DRIVE_SYSTEM_INDEPENDENT
                
                # Key Rebinding Buttons
                elif not is_rebinding:
                    for key_name_id, rect in options_button_rects.items():
                        if key_name_id.startswith('bind_') and rect.collidepoint(mouse_pos):
                            key_id = key_name_id.split('_')[1]
                            # Start rebinding process
                            key_names = {
                                'f': "Forward", 'r': "Reverse", 'l': "Turn Left", 's': "Turn Right",
                                'lf': "Left Track Forward", 'lr': "Left Track Reverse", 
                                'rf': "Right Track Forward", 'rr': "Right Track Reverse"
                            }
                            is_rebinding = True
                            rebinding_key_name = key_names.get(key_id, key_id.upper())
                            break


    keys = pygame.key.get_pressed()
    mouse_pos = pygame.mouse.get_pos()
    
    # --- Listener Position (Player's World Coordinates) ---
    listener_x = player_tank.x
    listener_y = player_tank.y
    
    # ------------------ UPDATE LOGIC ------------------
    if not game_over and game_state == STATE_GAMEPLAY:
        
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
                # --- FRIENDLY TANK AI --- (Logic remains the same, uses default keys)
                
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
                
                # 3. Movement
                # Friendly AI tanks use the default/standard movement update
                tank.update_movement(friendly_keys, is_player=False, features=terrain_features) 
                 
                # 4. Cooldown
                if tank.fire_cooldown > 0:
                    tank.fire_cooldown -= 1


        # --- CAMERA OFFSET CALCULATION (Independent of game state) ---
        ideal_offset_x = SCREEN_WIDTH // 2 - listener_x
        ideal_offset_y = SCREEN_HEIGHT // 2 - listener_y
        
        # Clamp camera to world boundaries
        max_offset_x = -WORLD_MIN_X 
        max_offset_y = -WORLD_MIN_Y 
        min_offset_x = SCREEN_WIDTH - WORLD_MAX_X 
        min_offset_y = SCREEN_HEIGHT - WORLD_MAX_Y 
        
        camera_offset_x = max(min_offset_x, min(max_offset_x, ideal_offset_x))
        camera_offset_y = max(min_offset_y, min(max_offset_y, ideal_offset_y))
        
        if game_state == STATE_GAMEPLAY:
            # Update bullets ONLY in gameplay state.
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


        # --- DYNAMIC CHUNK GENERATION (Only when player is alive) ---
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
    
    enemies_left = sum(1 for t in tanks if t.allegiance == 'Enemy' and t.is_alive)
    drive_mode_text = f"Drive: {player_tank.drive_system}"
    mode_text = f"HP: {player_tank.health} | Enemies Left: {enemies_left}"
    cooldown_text = f"Ready in: {max(0, player_tank.fire_cooldown) / FPS:.2f}s"
    angle_speed_text = f"Angle: {player_tank.angle:.2f} | Speed: {player_tank.speed:.2f}"
    fps_text = f"FPS: {real_fps:.2f}"
    
    if 'debug_font' in locals() and debug_font:
        text_surface_drive = debug_font.render(drive_mode_text, True, BLACK)
        text_surface_mode = debug_font.render(mode_text, True, BLACK)
        text_surface_cooldown = debug_font.render(cooldown_text, True, RED if player_tank.fire_cooldown > 0 else PLAYER_COLOR)
        text_surface_angle_speed = debug_font.render(angle_speed_text, True, BLACK)
        text_surface_fps = debug_font.render(fps_text, True, BLACK)
    
        screen.blit(text_surface_drive, (10, 10))
        screen.blit(text_surface_mode, (10, 40))
        screen.blit(text_surface_cooldown, (10, 70))
        screen.blit(text_surface_angle_speed, (10, 100))
        screen.blit(text_surface_fps, (10, 130))
    
    # --- GAME OVER SCREEN & RESTART BUTTON ---
    if game_over:
        # Drawing game over menu (remains the same)
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

    elif game_state == STATE_PAUSED:
        draw_pause_menu()
        restart_button_rect = None
        
    elif game_state == STATE_OPTIONS:
        draw_options_menu()
        restart_button_rect = None
        
    else:
        # Reset button rect when game is active to prevent accidental clicks
        restart_button_rect = None
        # options_button_rects is managed within draw_pause/options_menu for each call

    # Update the entire screen
    pygame.display.flip()
    
    # Limit FPS
    clock.tick(FPS)

pygame.quit()
