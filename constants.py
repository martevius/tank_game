import os
import pygame

# --- SCREEN & GAME SETTINGS ---
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
FPS = 60

# --- GAME STATES ---
STATE_GAMEPLAY = 0
STATE_PAUSED = 1
STATE_OPTIONS = 2

# --- DRIVE SYSTEMS ---
DRIVE_SYSTEM_STANDARD = 'Standard'
DRIVE_SYSTEM_INDEPENDENT = 'Independent'
DEFAULT_DRIVE_SYSTEM = DRIVE_SYSTEM_INDEPENDENT

# --- WORLD SETTINGS ---
CHUNK_SIZE = 500  # Size of a single terrain chunk in world units
FEATURE_DENSITY = 0.005 # Probability of placing an obstacle at a given coordinate ##0.0005 originally
WORLD_MIN_X, WORLD_MAX_X = -3000, 3000
WORLD_MIN_Y, WORLD_MAX_Y = -3000, 3000
WORLD_SIZE_X = WORLD_MAX_X - WORLD_MIN_X
WORLD_SIZE_Y = WORLD_MAX_Y - WORLD_MIN_Y

# --- TANK PARAMETERS ---
TANK_WIDTH = 60
TANK_HEIGHT = 90
TANK_ACCEL = 0.1
TANK_MAX_SPEED = 3.0
BASE_TURN_RATE = 1.0 # Degrees per frame
MAX_HEALTH = 100

# --- TURRET PARAMETERS ---
TURRET_ROTATION_SPEED = 1.5 # Degrees per frame

# --- PLAYER CONTROLS (DEFAULT BINDINGS) ---
# Standard Drive Keys
KEY_FORWARD = pygame.K_w
KEY_REVERSE = pygame.K_r
KEY_TURN_LEFT = pygame.K_a
KEY_TURN_RIGHT = pygame.K_s

# Independent Track Drive Keys
KEY_LEFT_FORWARD = pygame.K_q
KEY_LEFT_REVERSE = pygame.K_a
KEY_RIGHT_FORWARD = pygame.K_w
KEY_RIGHT_REVERSE = pygame.K_r

# Pause Key
KEY_PAUSE = pygame.K_p
KEY_OPTIONS = pygame.K_o


# --- TURRET & WEAPONS ---
TURRET_LENGTH = 50
TURRET_LINE_WIDTH = 8
FIRE_COOLDOWN_FRAMES = 180 # 1 second cooldown at 60 FPS ## changed from 60 to 180
BULLET_SPEED = 10.0
BULLET_RADIUS = 5
BULLET_DAMAGE = 25
BULLET_LIFESPAN = 200 # Frames (5 seconds) ## 300 frames is 5 seconds
MAX_BULLET_RANGE = 500 # Max range before bullet despawns orig 600

# --- COLORS (R, G, B) ---
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (200, 50, 50)
YELLOW = (255, 255, 0)
GREEN = (100, 150, 50) # Map Background
BROWN = (139, 69, 19) # Terrain Features (Obstacles)
DARK_GRAY = (50, 50, 50)
PLAYER_COLOR = (50, 150, 200) # Blueish for player
ENEMY_COLOR = (200, 50, 50) # Redish for enemies
BOUNDARY_COLOR = (255, 0, 0)
HP_BAR_GREEN = (0, 200, 0)
WRECK_COLOR_BODY = (80, 80, 80)
WRECK_COLOR_SMOKE = (150, 150, 150)

# --- SOUND & AUDIO SETTINGS ---
SOUND_VOLUME = 0.2 # Must be between 0.0 and 1.0
MAX_SOUND_DISTANCE = 1000 # Distance in world units at which sound is fully attenuated

# File paths (assuming 'sounds' folder in the same directory)
SOUND_DIR = 'sounds'
SOUND_FIRE_PATH = os.path.join(SOUND_DIR, 'fire.wav')
SOUND_EXPLOSION_PATH = os.path.join(SOUND_DIR, 'explosion.wav')
SOUND_HIT_PATH = os.path.join(SOUND_DIR, 'hit.wav')
