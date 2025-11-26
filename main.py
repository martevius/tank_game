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

def is_visible_on_screen(world_x, world_y, camera_offset_x, camera_offset_y):
    """Checks if a world coordinate is currently within the screen bounds."""
    # Convert world coordinates to screen coordinates
    screen_x = world_x + camera_offset_x
    screen_y = world_y + camera_offset_y
    
    # Check if the point is within the screen (with a small buffer)
    buffer = 0 # Add a small buffer around the screen edge
    
    return (screen_x > -buffer and screen_x < SCREEN_WIDTH + buffer and
            screen_y > -buffer and screen_y < SCREEN_HEIGHT + buffer)

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
friendly_tanks = pygame.sprite.Group()
all_friendly_tanks = pygame.sprite.Group()
player_tank = None # Will be initialized in initialize_game
game_over = False
game_result = ""
restart_button_rect = None # Stores the rect of the restart button for click detection
INDICATOR_MIN_LIFETIME = 40
#INDICATOR_BASE_LIFETIME_FRAMES = int(FPS * 0.75) # Base lifetime of the sound indicator is 3 seconds

# NEW: Sound Indicator List
active_sound_indicators = [] # Stores [IndicatorSprite, x, y] tuples

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
    all_friendly_tanks.add(new_player_tank)

    # Initialize Other Tanks (Pass sound objects)
    NUM_FRIENDLIES = 2
    NUM_ENEMIES = 3
    NUM_DUMMIES = 0

    for _ in range(NUM_FRIENDLIES):
        x, y = find_safe_spawn_position(terrain_features, min_dist=150, spawn_area_size=4)
        friendly = FriendlyAITank(x, y, fire_sound, explosion_sound) 
        tanks.add(friendly)
        friendly_tanks.add(friendly)
        all_friendly_tanks.add(friendly)

    for _ in range(NUM_ENEMIES):
        x, y = find_safe_spawn_position(terrain_features, min_dist=150, spawn_area_size=4)
        enemy = EnemyTank(x, y, fire_sound, explosion_sound) 
        tanks.add(enemy)

    for _ in range(NUM_DUMMIES):
        x, y = find_safe_spawn_position(terrain_features, min_dist=150, spawn_area_size=4)
        enemy = DummyEnemyTank(x, y, fire_sound, explosion_sound) 
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

    # RESET INDICATOR GROUP
    indicator_group.empty() # Call empty() to clear all IndicatorSprites

# Initial game setup
player_tank = initialize_game()

# ----------------------------------------------------
# --- UI DRAWING FUNCTIONS ---
# ----------------------------------------------------

# NEW FUNCTION: Draws a crosshair at the end of the turret line, indicating target direction
def draw_turret_crosshair(surface, tank, camera_offset_x, camera_offset_y):
    """Draws a crosshair at the projected point of the turret's line of sight."""
    
    # Tank's screen position
    center_screen_x = int(tank.x + camera_offset_x)
    center_screen_y = int(tank.y + camera_offset_y)

    # Calculate the end point of the turret line
    rad = math.radians(tank.turret_angle)
    
    # Use a longer length to make the crosshair more visible
    crosshair_length = TURRET_LENGTH + 50 
    
    end_x = center_screen_x + crosshair_length * math.cos(rad)
    end_y = center_screen_y - crosshair_length * math.sin(rad)
    
    # Draw the crosshair (small perpendicular lines)
    cross_size = 8
    
    # Horizontal line (relative to the tank)
    pygame.draw.line(surface, YELLOW, (end_x - cross_size, end_y), (end_x + cross_size, end_y), 2)
    
    # Vertical line (relative to the tank)
    pygame.draw.line(surface, YELLOW, (end_x, end_y - cross_size), (end_x, end_y + cross_size), 2)

# NEW FUNCTION: Draws a circle indicating the max bullet range
def draw_max_range_circle(surface, tank, camera_offset_x, camera_offset_y):
    """Draws a circle around the player indicating the bullet's maximum range."""
    
    # Center of the circle is the player's screen position
    center_screen_x = int(tank.x + camera_offset_x)
    center_screen_y = int(tank.y + camera_offset_y)
    
    # Radius is the max bullet range in screen pixels
    radius = MAX_BULLET_RANGE + 30
    
    # Draw a dashed or simple circle
    pygame.draw.circle(surface, RED, (center_screen_x, center_screen_y), radius, 1)


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


# --- NEW: SOUND INDICATOR SPRITE CLASS ---
class SoundIndicator(pygame.sprite.Sprite):
    def __init__(self, sound_type, x, y, volume, listener_x, listener_y):
        super().__init__()
        
        self.x, self.y = x, y # World position of the sound source
        self.sound_type = sound_type

        # FIX: Implement the requested 3-second base lifetime + a volume-dependent bonus.
        # This replaces the old, buggy logic that incorrectly set self.max_lifetime to a fixed 40 frames.
        
        # Volume bonus: 0 seconds for silent, up to 1 second for max volume.
        volume_bonus_seconds = volume * 1.0 
        volume_bonus_frames = int(FPS * volume_bonus_seconds)
        
        # The new max lifetime is the base (3s) + the volume bonus (0-1s).
        #self.max_lifetime = INDICATOR_BASE_LIFETIME_FRAMES + volume_bonus_frames
        
        # Set max_lifetime to at least the minimum, guaranteeing visibility
        #self.max_lifetime = max(INDICATOR_MIN_LIFETIME, base_lifetime)...
        self.max_lifetime = INDICATOR_MIN_LIFETIME # <-- BUGGY LINE REMOVED
        
        self.lifetime = self.max_lifetime 
        self.initial_volume = volume 
        self.alpha = 20
        self.angle = 0

        #initiate
        self.screen_x = 0
        self.screen_y = 0
        
        # Determine visual style
        if sound_type == 'explosion':
            self.color = RED
            self.label = "BOOM!"
            self.indicator_size = 15
        elif sound_type == 'fire':
            self.color = YELLOW
            self.label = "FIRE"
            self.indicator_size = 10
        elif sound_type == 'hit':
            self.color = WHITE
            self.label = "HIT"
            self.indicator_size = 8
        elif sound_type == 'player hit':
            self.color = RED
            self.label = "PLAYER HIT"
            self.indicator_size = 8
        else:
            self.color = WHITE
            self.label = "?"
            self.indicator_size = 5

    def update(self, listener_x, listener_y, camera_offset_x, camera_offset_y):
        """Update lifetime and calculate screen position/rotation."""
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.kill()
            return

        # ----------------------------------------------------
        # --- NEW: CHECK VISIBILITY AND KILL IF SOURCE IS ON-SCREEN ---
        # ----------------------------------------------------
        # Use the utility function to check if the sound source's world position (self.x, self.y) 
        # is currently visible to the player.
        """if self.sound_type != 'hit': 
            if is_visible_on_screen(self.x, self.y, camera_offset_x, camera_offset_y):
                self.kill() # Immediately remove the indicator if the source is seen
                return """
        
##        if is_visible_on_screen(self.x, self.y, camera_offset_x, camera_offset_y):
##                self.kill() # Immediately remove the indicator if the source is seen
##                return
            
        # Calculate vector from listener (player) to sound source
        dx = self.x - listener_x
        dy = self.y - listener_y
        distance = math.hypot(dx, dy)
        
        # Calculate angle of the sound source relative to the screen/player center
        # atan2(y, x) for angle from positive x-axis, then convert to degrees
        self.angle = math.degrees(math.atan2(-dy, dx)) # -dy because Pygame y-axis is inverted
        #self.angle = math.degrees(math.atan2(dy, -dx)) # -dy because Pygame y-axis is inverted
        #print(self.angle)

        # Determine how far to place the indicator on the screen (clamped to edge)
        # Use a distance greater than MAX_BULLET_RANGE to ensure it appears outside the range circle
        
        # Max distance on screen before clamping to the edge for the HUD element
        hud_radius = min(SCREEN_WIDTH, SCREEN_HEIGHT) * 0.45 
        
        # Place the indicator further out if the source is far, but clamp at the HUD radius
        distance_factor = min(1.0, distance / MAX_SOUND_DISTANCE) 
        
        # Use the HUD radius to place the indicator on the screen
        indicator_dist_from_center = hud_radius * (0.8 + 0.2 * distance_factor) # Place it slightly inside the edge
        
        # Calculate screen position based on angle and distance from screen center
        # Player is at (SCREEN_WIDTH/2, SCREEN_HEIGHT/2) in a non-scrolling HUD context
        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        
        self.screen_x = center_x + indicator_dist_from_center * math.cos(math.radians(self.angle))
        self.screen_y = center_y - indicator_dist_from_center * math.sin(math.radians(self.angle))
        
        # Fading: opacity based on remaining lifetime
        self.alpha = int(255 * (self.lifetime / self.max_lifetime))
        
        
    def draw(self, surface):
        """Draws the indicator (triangle pointing inwards) and text."""
        
        # Don't draw if not enough opacity or has expired
        if self.lifetime <= 0 or self.alpha < 10:
            #print("not drawn")
            return
            
        current_color = (self.color[0], self.color[1], self.color[2], self.alpha)
        
        # 1. Draw the Directional Triangle (Arrow)
        arrow_size = self.indicator_size
        
        # Calculate the base of the triangle (perpendicular to the direction vector)
        rad = math.radians(self.angle)
        
        # The center of the indicator is self.screen_x, self.screen_y
        
        # The base of the arrow faces the player
        base_angle_rad = rad + math.pi / 2 # Perpendicular
        
        p1_x = self.screen_x + arrow_size * math.cos(rad)
        p1_y = self.screen_y - arrow_size * math.sin(rad)

        p2_x = self.screen_x + arrow_size * math.cos(base_angle_rad)
        p2_y = self.screen_y - arrow_size * math.sin(base_angle_rad)
        
        p3_x = self.screen_x - arrow_size * math.cos(base_angle_rad)
        p3_y = self.screen_y + arrow_size * math.sin(base_angle_rad)
        
        # Create a surface with per-pixel alpha for the colored triangle
        arrow_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        pygame.draw.polygon(arrow_surface, current_color, [(p1_x, p1_y), (p2_x, p2_y), (p3_x, p3_y)])
        surface.blit(arrow_surface, (0, 0)) # Blit the whole surface
        
        # 2. Draw the Text Label (Fading)
        # Temporarily use the small font initialized earlier
        try:
            # Render with a slight distance away from the triangle
            text_x = self.screen_x + (arrow_size + 5) * math.cos(rad)
            text_y = self.screen_y - (arrow_size + 5) * math.sin(rad)
            
            # Text should be rendered with opacity (not directly supported by pygame.font)
            # We'll stick to full opacity text and let the triangle fade, or use an overlay trick
            
            # Simple text rendering (no fade on text to simplify)
            text_surface = small_font.render(self.label, True, self.color)
            text_rect = text_surface.get_rect(center=(int(text_x), int(text_y)))
            surface.blit(text_surface, text_rect)
            
        except NameError:
             # Fallback if small_font isn't available (shouldn't happen)
             pass


# Create a new sprite group for indicators
indicator_group = pygame.sprite.Group()



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

        # --- NEW: Handle player's own fire sound ---
##        player_fire_event = player_tank.fire(bullets)
##        if player_fire_event:
##            # Unpack the sound event: [sound_type, x, y, volume]
##            s_type, s_x, s_y, s_vol = player_fire_event
##            new_indicator = SoundIndicator(s_type, s_x, s_y, s_vol, listener_x, listener_y)
##            indicator_group.add(new_indicator)
        
        
        enemies_left = 0
        # Assuming 'player_tank' is the PlayerTank object and 'friendly_tanks' is a list of other friendly AI
        
        
        for tank in tanks:
            if isinstance(tank, EnemyTank):
                # Enemy update requires the bullets group to fire
                sound_event = tank.update(all_friendly_tanks, player_tank.x, player_tank.y, terrain_features, bullets) 
                if tank.is_alive:
                    enemies_left += 1

                if sound_event:
                    s_type, s_x, s_y, s_vol = sound_event
                    new_indicator = SoundIndicator(s_type, s_x, s_y, s_vol, listener_x, listener_y)
                    indicator_group.add(new_indicator)
            elif tank != player_tank and tank.is_alive:
                # --- FRIENDLY TANK AI --- (Logic remains the same, uses default keys)
                
                # 1. Target Acquisition (Find the nearest enemy)
                nearest_enemy = None
                min_dist_sq = float('inf')
                
                
                    
                
                for enemy in tanks:
                    # Only consider active enemies
                    if enemy.allegiance == 'Enemy' and enemy.is_alive:
                        dist_sq = (tank.x - enemy.x)**2 + (tank.y - enemy.y)**2
                        #print(dist_sq)
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
                        
                        #print("fired")
                        sound_event = tank.fire(bullets, player_tank.x, player_tank.y)
                        #print("tank fired")
                        if sound_event:
                            s_type, s_x, s_y, s_vol = sound_event
                            new_indicator = SoundIndicator(s_type, s_x, s_y, s_vol, listener_x, listener_y)
                            indicator_group.add(new_indicator)
                        
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
                        # --- NEW: Capture Take Damage/Explosion Sound Event ---
                        sound_event = tank_hit.take_damage(BULLET_DAMAGE, listener_x, listener_y)
##                        if sound_event:
##                            print("hit")
##                            s_type, s_x, s_y, s_vol = sound_event
##                            new_indicator = SoundIndicator(s_type, s_x, s_y, s_vol, listener_x, listener_y)
##                            indicator_group.add(new_indicator)
                            
                        bullet.kill()

                        # HIT SOUND: Volume must be calculated here...

                        # --- FIX: Recalculate final_volume for the HIT sound ---
                        # Note: The Tank class has a private method for this, we must replicate its logic here:
                        
                        # Calculate distance between player (listener) and the hit tank (sound source)
                        dist = math.hypot(tank_hit.x - listener_x, tank_hit.y - listener_y)

                        # Calculate final volume (0.0 to 1.0)
                        # Assumes MAX_SOUND_DISTANCE is defined in constants.py (or uses 1000 as a default range)
                        MAX_SOUND_DISTANCE = 1500 # Assume a value if not in constants (check constants.py)

                        # Simple linear volume falloff
                        if dist >= MAX_SOUND_DISTANCE:
                            final_volume = 0.0
                        else:
                            final_volume = max(0.0, 1.0 - (dist / MAX_SOUND_DISTANCE))

                        # Play hit sound with distance volume
                        hit_sound.set_volume(final_volume)
                        hit_sound.play()
                        
                        # ... (lines 393-401 of original main.py - remains the same)
                        # --- NEW: Add a separate indicator for HIT sound ---
                        # Hit sound is non-positional, so its indicator is always centered/fading
                        if final_volume > 0.0:
                            # Use player's position as the sound location for a non-directional indicator
                            #print("hit")
                            if tank_hit != player_tank:
                                hit_indicator = SoundIndicator('hit', tank_hit.x, tank_hit.y, final_volume, listener_x, listener_y) 
                                indicator_group.add(hit_indicator)
                            elif tank_hit == player_tank:
                                hit_indicator = SoundIndicator('player hit', tank_hit.x, tank_hit.y, final_volume, listener_x, listener_y)
                                indicator_group.add(hit_indicator)

                        break

                # --- UPDATE SOUND INDICATORS ---
                # Pass the player's position and camera offset for world-to-screen conversion
                for indicator in indicator_group:
                    indicator.update(listener_x, listener_y, camera_offset_x, camera_offset_y)

                    """    
                    # HIT SOUND: Volume must be calculated here since the sound object belongs to main.py
                    distance = math.hypot(bullet.x - listener_x, bullet.y - listener_y)
                    volume_ratio = 1.0 - (distance / MAX_SOUND_DISTANCE)
                    # Apply a base factor (0.7) and clamp the volume
                    final_volume = max(0.0, min(1.0, volume_ratio)) * SOUND_VOLUME * 0.7 
                        
                    hit_sound.set_volume(final_volume)
                    hit_sound.play() 
                    break  """
                        
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

    # NEW: Draw Player-specific UI only when in gameplay state
    if player_tank.is_alive and game_state == STATE_GAMEPLAY:
        draw_turret_crosshair(screen, player_tank, camera_offset_x, camera_offset_y)
        draw_max_range_circle(screen, player_tank, camera_offset_x, camera_offset_y)

    # NEW: Draw sound indicators (MUST be last to be on top of everything)
    if game_state == STATE_GAMEPLAY:
        for indicator in indicator_group:
            indicator.draw(screen)
    
    # Draw debug/info text
    real_fps = clock.get_fps() 
    
    enemies_left = sum(1 for t in tanks if t.allegiance == 'Enemy' and t.is_alive)
    drive_mode_text = f"Drive: {player_tank.drive_system}"
    mode_text = f"HP: {player_tank.health} | Enemies Left: {enemies_left}"
    
    angle_speed_text = f"Angle: {player_tank.angle:.2f} | Speed: {player_tank.speed:.2f}"
    fps_text = f"FPS: {real_fps:.2f}"
    cooldown_text = f"Ready in: {max(0, player_tank.fire_cooldown) / FPS:.2f}s"
    
    if 'debug_font' in locals() and debug_font:
        text_surface_drive = debug_font.render(drive_mode_text, True, BLACK)
        text_surface_mode = debug_font.render(mode_text, True, BLACK)
        
        text_surface_angle_speed = debug_font.render(angle_speed_text, True, BLACK)
        text_surface_fps = debug_font.render(fps_text, True, BLACK)
        text_surface_cooldown = debug_font.render(cooldown_text, True, RED if player_tank.fire_cooldown > 0 else PLAYER_COLOR)
    
        screen.blit(text_surface_drive, (10, 10))
        screen.blit(text_surface_mode, (10, 40))
        
        screen.blit(text_surface_angle_speed, (10, 100))
        screen.blit(text_surface_fps, (10, 130))
        screen.blit(text_surface_cooldown, (10, 70))
    
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
