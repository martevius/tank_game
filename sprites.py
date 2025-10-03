import pygame
import math
import random
from constants import *
# Note: terrain_features list is defined in main.py and passed/accessed globally via update calls

# ----------------------------------------------------
# --- BULLET CLASS ---
# ----------------------------------------------------
class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, angle, color):
        super().__init__()
        
        self.x = x
        self.y = y
        self.angle = angle
        self.start_x = x 
        self.start_y = y 
        
        # Calculate velocity components
        self.vx = BULLET_SPEED * math.cos(math.radians(self.angle))
        self.vy = BULLET_SPEED * math.sin(math.radians(self.angle))
        
        # Create a simple circular surface for the bullet
        self.image = pygame.Surface((BULLET_RADIUS * 2, BULLET_RADIUS * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, color, (BULLET_RADIUS, BULLET_RADIUS), BULLET_RADIUS)
        self.rect = self.image.get_rect(center=(x, y))
        
        self.lifespan = BULLET_LIFESPAN

    def update(self, camera_offset_x, camera_offset_y, features):
        """Updates bullet position, checks range, lifespan, bounds, and terrain collision."""
        self.x += self.vx
        self.y -= self.vy 
        
        # Update screen position using camera offset
        self.rect.centerx = int(self.x + camera_offset_x)
        self.rect.centery = int(self.y + camera_offset_y)

        # 1. Check Maximum Range
        distance_sq = (self.x - self.start_x)**2 + (self.y - self.start_y)**2
        if distance_sq > MAX_BULLET_RANGE**2:
            self.kill()
            return

        # 2. Check Lifespan
        self.lifespan -= 1
        if self.lifespan <= 0: 
            self.kill() 
            return

        # 3. Check World Bounds
        if (self.x < WORLD_MIN_X or self.x > WORLD_MAX_X or 
            self.y < WORLD_MIN_Y or self.y > WORLD_MAX_Y):
            self.kill()
            return
            
        # 4. Check Collision with terrain features
        bullet_rect_world = pygame.Rect(self.x - BULLET_RADIUS, self.y - BULLET_RADIUS, BULLET_RADIUS * 2, BULLET_RADIUS * 2)
        for feature in features:
            if bullet_rect_world.colliderect(feature):
                self.kill() 
                return

# ----------------------------------------------------
# --- TANK BASE CLASS ---
# ----------------------------------------------------
class Tank(pygame.sprite.Sprite):
    def __init__(self, x, y, allegiance, fire_sound, explosion_sound):
        super().__init__()
        self.allegiance = allegiance 
        self.color = PLAYER_COLOR if allegiance == 'Friendly' else ENEMY_COLOR
        self.bullet_color = YELLOW if allegiance == 'Friendly' else RED

        self.max_health = MAX_HEALTH
        self.health = MAX_HEALTH
        self.is_alive = True
        self.is_wreck = False
        
        self.fire_sound = fire_sound
        self.explosion_sound = explosion_sound

        self.image = pygame.Surface((TANK_WIDTH, TANK_HEIGHT), pygame.SRCALPHA)
        self.image.fill((0,0,0,0))
        self.x, self.y = float(x), float(y)
        self.rect = self.image.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        self.angle = random.randint(0, 360) 
        self.turret_angle = 90
        self.speed = 0.0
        self.fire_cooldown = 0 
        
    def _calculate_volume(self, player_x, player_y):
        """Calculates volume based on distance to the player (the listener)."""
        if MAX_SOUND_DISTANCE <= 0:
            return SOUND_VOLUME
            
        distance = math.hypot(self.x - player_x, self.y - player_y)
        
        # Linear falloff: 1.0 at distance 0, 0.0 at MAX_SOUND_DISTANCE
        volume_ratio = 1.0 - (distance / MAX_SOUND_DISTANCE)
        
        # Clamp and multiply by base volume
        final_volume = max(0.0, min(1.0, volume_ratio)) * SOUND_VOLUME
        return final_volume

    def take_damage(self, damage, player_x, player_y):
        """Calculates damage and plays explosion sound with distance volume."""
        if not self.is_alive: return 
        
        self.health -= damage
        
        if self.health <= 0:
            self.health = 0
            
            # Play explosion sound on destruction with distance volume
            if self.is_alive:
                final_volume = self._calculate_volume(player_x, player_y)
                self.explosion_sound.set_volume(final_volume)
                self.explosion_sound.play()
                
            self.is_alive = False
            self.is_wreck = True
            self.speed = 0.0

    def fire(self, bullets_group, player_x, player_y): 
        """Spawns a bullet if the tank is alive and the cooldown is ready."""
        if not self.is_alive or self.fire_cooldown > 0: 
            return
        
        # Play firing sound with distance volume
        final_volume = self._calculate_volume(player_x, player_y)
        self.fire_sound.set_volume(final_volume)
        self.fire_sound.play()
            
        # Calculate bullet spawn point at the tip of the turret
        rad = math.radians(self.turret_angle)
        spawn_offset_x = TURRET_LENGTH * math.cos(rad)
        spawn_offset_y = TURRET_LENGTH * math.sin(rad)
        
        bullet_start_x = self.x + spawn_offset_x
        bullet_start_y = self.y - spawn_offset_y 

        new_bullet = Bullet(bullet_start_x, bullet_start_y, self.turret_angle, self.bullet_color)
        bullets_group.add(new_bullet)
        
        # Reset cooldown
        self.fire_cooldown = FIRE_COOLDOWN_FRAMES

    def update_movement(self, keys, is_player, features, drive_system=DRIVE_SYSTEM_STANDARD, control_keys=None):
        """Handles acceleration, turning, collision detection, and world boundary checks."""
        if not self.is_alive: return
        
        if is_player and drive_system == DRIVE_SYSTEM_INDEPENDENT:
            # --- INDEPENDENT TRACK DRIVE LOGIC ---
            
            # Use provided control_keys, or fall back to defaults if not provided (shouldn't happen for player)
            controls = control_keys if control_keys else {
                'lf': KEY_LEFT_FORWARD, 'lr': KEY_LEFT_REVERSE,
                'rf': KEY_RIGHT_FORWARD, 'rr': KEY_RIGHT_REVERSE
            }

            left_forward = keys[controls['lf']]
            left_reverse = keys[controls['lr']]
            right_forward = keys[controls['rf']]
            right_reverse = keys[controls['rr']]

            left_speed = (left_forward - left_reverse) * TANK_MAX_SPEED
            right_speed = (right_forward - right_reverse) * TANK_MAX_SPEED
            
            # Average forward speed
            avg_speed = (left_speed + right_speed) / 2.0
            
            # Differential speed for turning
            turn_speed = (right_speed - left_speed) * 0.5 # Factor to control turn rate
            
            # Update angle (turning is instantaneous based on speed differential)
            self.angle -= turn_speed / TANK_MAX_SPEED * BASE_TURN_RATE * 2.5 # Adjust multiplier for desired turn rate
            self.angle %= 360

            # Set self.speed for collision/velocity logic
            # This is simplified: in a true physics simulation, speed is not a single value.
            # Here, we use the average speed to determine the forward motion.
            self.speed = avg_speed
            
            # Note: TANK_ACCEL logic is bypassed in this mode for simplicity
            
        elif is_player and drive_system == DRIVE_SYSTEM_STANDARD:
            # --- STANDARD DRIVE LOGIC (Original) ---
            
            # Use provided control_keys, or fall back to defaults
            controls = control_keys if control_keys else {
                'f': KEY_FORWARD, 'r': KEY_REVERSE,
                'l': KEY_TURN_LEFT, 's': KEY_TURN_RIGHT
            }
            
            is_forward_throttle = keys[controls['f']]
            is_reverse_throttle = keys[controls['r']]
            is_turning_left = keys[controls['l']]
            is_turning_right = keys[controls['s']]
            
            # Throttle (Acceleration/Deceleration)
            if is_forward_throttle: 
                self.speed = min(self.speed + TANK_ACCEL, TANK_MAX_SPEED)
            elif is_reverse_throttle: 
                self.speed = max(self.speed - TANK_ACCEL, -TANK_MAX_SPEED / 2)
            else:
                if self.speed > 0:
                    self.speed = max(0.0, self.speed - TANK_ACCEL / 2)
                elif self.speed < 0:
                    self.speed = min(0.0, self.speed + TANK_ACCEL / 2)

            # Steering
            current_abs_speed = abs(self.speed)
            # Speed factor logic... (Original code)
            speed_factor = 1.0 + (TANK_MAX_SPEED - current_abs_speed) / TANK_MAX_SPEED if TANK_MAX_SPEED > 0 else 1.0
            dynamic_turn_rate = BASE_TURN_RATE * speed_factor

            if current_abs_speed > 0.01 and (is_turning_left or is_turning_right): 
                turn_direction = 1 if self.speed > 0 else -1
                if is_turning_left: self.angle -= dynamic_turn_rate * turn_direction
                elif is_turning_right: self.angle += dynamic_turn_rate * turn_direction
            
        else: # AI Tank Logic (simplified)
            # Enemy/Friendly Tank Logic (uses internal keys dict)
            is_forward_throttle = keys.get(pygame.K_w, False) 
            is_reverse_throttle = keys.get(pygame.K_r, False)
            is_turning_left = keys.get(pygame.K_a, False)     
            is_turning_right = keys.get(pygame.K_s, False)

            # Throttle (Acceleration/Deceleration) - AI logic remains the same
            if is_forward_throttle: 
                self.speed = min(self.speed + TANK_ACCEL, TANK_MAX_SPEED)
            elif is_reverse_throttle: 
                self.speed = max(self.speed - TANK_ACCEL, -TANK_MAX_SPEED / 2)
            else:
                if self.speed > 0:
                    self.speed = max(0.0, self.speed - TANK_ACCEL / 2)
                elif self.speed < 0:
                    self.speed = min(0.0, self.speed + TANK_ACCEL / 2)
                    
            # Steering - AI logic remains the same
            current_abs_speed = abs(self.speed)
            speed_factor = 1.0 + (TANK_MAX_SPEED - current_abs_speed) / TANK_MAX_SPEED if TANK_MAX_SPEED > 0 else 1.0
            dynamic_turn_rate = BASE_TURN_RATE * speed_factor

            if current_abs_speed > 0.01 and (is_turning_left or is_turning_right): 
                turn_direction = 1 if self.speed > 0 else -1
                if is_turning_left: self.angle -= dynamic_turn_rate * turn_direction
                elif is_turning_right: self.angle += dynamic_turn_rate * turn_direction


        # Calculate Potential Movement (Same for all drive modes)
        # Note: self.angle is updated by both drive modes
        new_x = self.x + self.speed * math.cos(math.radians(self.angle - 90))
        new_y = self.y + self.speed * math.sin(math.radians(self.angle - 90))

        # Collision Detection (Obstacles)
        temp_rect = pygame.Rect(new_x - TANK_WIDTH / 2, new_y - TANK_HEIGHT / 2, TANK_WIDTH, TANK_HEIGHT)
        is_colliding = False
        for feature in features:
            if temp_rect.colliderect(feature):
                is_colliding = True
                break

        if is_colliding:
            self.speed = 0.0
        else:
            self.x, self.y = new_x, new_y
        
        # World Boundary Clamping
        half_width, half_height = TANK_WIDTH / 2, TANK_HEIGHT / 2
        clamped_x = max(WORLD_MIN_X + half_width, min(self.x, WORLD_MAX_X - half_width))
        clamped_y = max(WORLD_MIN_Y + half_height, min(self.y, WORLD_MAX_Y - half_height))
        
        if self.x != clamped_x or self.y != clamped_y:
            self.speed = 0.0
        
        self.x, self.y = clamped_x, clamped_y


    def rotate_turret(self, target_angle):
        if not self.is_alive: return 
        self.turret_angle = target_angle
        
    def draw(self, surface, camera_offset_x, camera_offset_y):
        """Draws the tank body, turret, wreck, and health bar with improved aesthetics."""
        
        # 1. Update rect position for screen drawing
        self.rect.centerx = int(self.x + camera_offset_x)
        self.rect.centery = int(self.y + camera_offset_y)
        center_screen = self.rect.center

        # Determine draw color
        body_color = WRECK_COLOR_BODY if self.is_wreck else self.color
        track_color = DARK_GRAY
        
        # 2. Draw Body and Tracks (Rotation is complex, so we'll draw shapes relative to the center)
        
        # Create a temporary surface to draw the non-rotated body parts
        temp_surface = pygame.Surface((TANK_WIDTH, TANK_HEIGHT), pygame.SRCALPHA)
        
        # Body (Rounded Rectangle) - slightly smaller to show the tracks outside
        body_rect = pygame.Rect(TANK_WIDTH * 0.1, TANK_HEIGHT * 0.1, TANK_WIDTH * 0.8, TANK_HEIGHT * 0.8)
        pygame.draw.rect(temp_surface, body_color, body_rect, border_radius=5)
        
        # Tracks (Using rectangles on the sides)
        track_width = TANK_WIDTH * 0.15
        
        # Left Track
        track_rect_l = pygame.Rect(0, 0, track_width, TANK_HEIGHT)
        pygame.draw.rect(temp_surface, track_color, track_rect_l, border_radius=3)
        
        # Right Track
        track_rect_r = pygame.Rect(TANK_WIDTH - track_width, 0, track_width, TANK_HEIGHT)
        pygame.draw.rect(temp_surface, track_color, track_rect_r, border_radius=3)
        
        # Rotate the tank body
        rotated_tank = pygame.transform.rotate(temp_surface, -self.angle) 
        tank_rect = rotated_tank.get_rect(center=center_screen)
        surface.blit(rotated_tank, tank_rect.topleft)
        
        if self.is_wreck:
            # WRECK details: smoke circle and black hole
            pygame.draw.circle(surface, WRECK_COLOR_SMOKE, center_screen, TANK_WIDTH // 3, 0)
            pygame.draw.circle(surface, BLACK, center_screen, TANK_WIDTH // 6, 0)
            return

        # 3. Draw Turret and Gun Barrel (No Rotation needed, uses turret_angle)
        
        # Turret Base (A circle centered on the tank's screen center)
        pygame.draw.circle(surface, DARK_GRAY, center_screen, TANK_WIDTH // 4)
        
        # Gun Barrel (Line from center to tip)
        end_x = center_screen[0] + TURRET_LENGTH * math.cos(math.radians(self.turret_angle))
        end_y = center_screen[1] - TURRET_LENGTH * math.sin(math.radians(self.turret_angle))
        pygame.draw.line(surface, BLACK, center_screen, (end_x, end_y), TURRET_LINE_WIDTH)

        # 4. Health Bar (Drawn above the tank)
        health_bar_width, health_bar_height = TANK_WIDTH, 5
        health_ratio = self.health / self.max_health
        current_hp_width = int(health_bar_width * health_ratio)

        hp_bg_rect = pygame.Rect(self.rect.left, self.rect.top - 10, health_bar_width, health_bar_height)
        pygame.draw.rect(surface, RED, hp_bg_rect)
        
        hp_rect = pygame.Rect(self.rect.left, self.rect.top - 10, current_hp_width, health_bar_height)
        pygame.draw.rect(surface, HP_BAR_GREEN, hp_rect)

# ----------------------------------------------------
# --- PLAYER TANK CLASS ---
# ----------------------------------------------------
class PlayerTank(Tank):
    def __init__(self, x, y, fire_sound, explosion_sound):
        super().__init__(x, y, 'Friendly', fire_sound, explosion_sound) 
        # Player-specific settings
        self.drive_system = DEFAULT_DRIVE_SYSTEM
        self.control_keys = {
            DRIVE_SYSTEM_STANDARD: {
                'f': KEY_FORWARD, 'r': KEY_REVERSE,
                'l': KEY_TURN_LEFT, 's': KEY_TURN_RIGHT
            },
            DRIVE_SYSTEM_INDEPENDENT: {
                'lf': KEY_LEFT_FORWARD, 'lr': KEY_LEFT_REVERSE,
                'rf': KEY_RIGHT_FORWARD, 'rr': KEY_RIGHT_REVERSE
            }
        }
        
    def update(self, keys, mouse_pos, features):
        """Handles player input for movement and decrements cooldown."""
        
        # Pass the current drive system and control keys to the base class
        self.update_movement(
            keys, 
            is_player=True, 
            features=features, 
            drive_system=self.drive_system,
            control_keys=self.control_keys[self.drive_system]
        )
        
        if self.fire_cooldown > 0:
            self.fire_cooldown -= 1
        
        if self.is_alive:
            # Turret Aiming (uses mouse position relative to the tank's screen position)
            dx = mouse_pos[0] - self.rect.centerx
            dy = mouse_pos[1] - self.rect.centery
            target_angle = math.degrees(math.atan2(-dy, dx))
            self.rotate_turret(target_angle)
            
    def fire(self, bullets_group): 
        """Player fire method, calls base fire and uses its own coordinates for max volume."""
        # FIX: Ensure we call the super method with the required world coordinates (self.x, self.y)
        super().fire(bullets_group, self.x, self.y)

# ----------------------------------------------------
# --- ENEMY TANK CLASS ---
# ----------------------------------------------------
class EnemyTank(Tank):
    def __init__(self, x, y, fire_sound, explosion_sound):
        super().__init__(x, y, 'Enemy', fire_sound, explosion_sound)
        self.move_timer = 0
        self.ai_keys = {
            pygame.K_w: False, 
            pygame.K_r: False, 
            pygame.K_a: False, 
            pygame.K_s: False
        }

    def update(self, player_tank, features, bullets_group): 
        """Handles enemy AI movement, tracking, firing, and decrements cooldown."""
        if not self.is_alive: return

        # 1. Decrement Cooldown
        if self.fire_cooldown > 0:
            self.fire_cooldown -= 1

        # 2. AI Movement (Simple random movement cycle)
        self.move_timer -= 1
        if self.move_timer <= 0:
            self.move_timer = random.randint(30, 120) 
            self.ai_keys = {pygame.K_w: False, pygame.K_r: False, pygame.K_a: False, pygame.K_s: False}
            action = random.choice(['forward', 'turn_left', 'turn_right', 'stop'])
            
            if action == 'forward':
                self.ai_keys[pygame.K_w] = True
            elif action == 'turn_left':
                self.ai_keys[pygame.K_w] = True 
                self.ai_keys[pygame.K_a] = True
            elif action == 'turn_right':
                self.ai_keys[pygame.K_w] = True 
                self.ai_keys[pygame.K_s] = True

        # AI tanks always use the simple, standard drive logic
        self.update_movement(self.ai_keys, is_player=False, features=features)
        
        # 3. Turret Tracking (Aims at player)
        dx = player_tank.x - self.x
        dy = player_tank.y - self.y
        target_angle = math.degrees(math.atan2(-dy, dx))
        self.rotate_turret(target_angle)
        
        # 4. Firing 
        if self.fire_cooldown == 0:
            if random.random() < 0.1: 
                # Enemy firing must pass the player's world coordinates for volume calculation
                self.fire(bullets_group, player_tank.x, player_tank.y)
