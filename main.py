from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
import random
import sqlite3

app = FastAPI()

# Database setup
DATABASE_URL = "game.db"  # SQLite database file
conn = sqlite3.connect(DATABASE_URL, check_same_thread=False)
cursor = conn.cursor()

# Create tables (if they don't exist)
cursor.execute("""
CREATE TABLE IF NOT EXISTS cards (
    name TEXT PRIMARY KEY,
    suit TEXT,
    value INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY,
    name TEXT,
    hp INTEGER DEFAULT 4,
    max_hp INTEGER DEFAULT 5,
    role TEXT,
    is_alive INTEGER DEFAULT 1,  -- 1 for True, 0 for False
    is_ready INTEGER DEFAULT 0,
    position INTEGER DEFAULT 0,
    weapon TEXT DEFAULT 'Кольт',
    permanent_effects TEXT DEFAULT '[]'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS game_rooms (
    id INTEGER PRIMARY KEY,
    game_started INTEGER DEFAULT 0,
    current_player_id INTEGER,
    roles_assigned INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS player_hands (
    player_id INTEGER,
    card_name TEXT,
    FOREIGN KEY (player_id) REFERENCES players(id),
    FOREIGN KEY (card_name) REFERENCES cards(name),
    PRIMARY KEY (player_id, card_name)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS deck (
    room_id INTEGER,
    card_name TEXT,
    position INTEGER,  -- Order in the deck
    FOREIGN KEY (room_id) REFERENCES game_rooms(id),
    FOREIGN KEY (card_name) REFERENCES cards(name),
    PRIMARY KEY (room_id, card_name)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS discard_pile (
    room_id INTEGER,
    card_name TEXT,
    FOREIGN KEY (room_id) REFERENCES game_rooms(id),
    FOREIGN KEY (card_name) REFERENCES cards(name),
    PRIMARY KEY (room_id, card_name)
)
""")

conn.commit()


# Models (using Pydantic for API interaction, not directly for database)
class Card(BaseModel):
    name: str
    suit: Optional[str] = None
    value: Optional[int] = None


class Player(BaseModel):
    id: int
    name: str
    hp: int
    max_hp: int
    hand: List[Card]  # Updated type hint
    role: Optional[str] = None
    is_alive: bool
    is_ready: bool
    position: int
    weapon: str
    permanent_effects: List[str]  # Storing as list


class GameRoom(BaseModel):
    id: int
    players: Dict[int, Player]  # Updated type hint
    game_started: bool
    current_player_id: Optional[int]
    roles_assigned: bool


# Constants
WEAPONS = {
    "Кольт": 1,
    "Скофилд": 2,
    "Ремингтон": 3,
    "Карабин": 4,
    "Винчестер": 5,
    "Воканчик": 1,
}


# Database Helper Functions
def db_get_card(card_name: str) -> Optional[Card]:
    cursor.execute("SELECT name, suit, value FROM cards WHERE name = ?", (card_name,))
    row = cursor.fetchone()
    if row:
        name, suit, value = row
        return Card(name=name, suit=suit, value=value)
    return None


def db_add_card(card: Card):
    try:
        cursor.execute("INSERT INTO cards (name, suit, value) VALUES (?, ?, ?)",
                       (card.name, card.suit, card.value))
        conn.commit()
    except sqlite3.IntegrityError:
        # Card already exists, you can handle this as needed (e.g., update)
        pass


def db_get_player(player_id: int) -> Optional[Player]:
    cursor.execute(
        "SELECT id, name, hp, max_hp, role, is_alive, is_ready, position, weapon, permanent_effects FROM players WHERE id = ?",
        (player_id,))
    row = cursor.fetchone()
    if row:
        id, name, hp, max_hp, role, is_alive, is_ready, position, weapon, permanent_effects_str = row
        # Fetch hand cards
        cursor.execute("SELECT card_name FROM player_hands WHERE player_id = ?", (id,))
        card_names = [row[0] for row in cursor.fetchall()]
        hand = [db_get_card(card_name) for card_name in card_names if db_get_card(card_name) is not None]

        # Parse permanent_effects
        try:
            permanent_effects = eval(permanent_effects_str)  # Be cautious when using eval
            if not isinstance(permanent_effects, list):
                permanent_effects = []
        except:
            permanent_effects = []

        return Player(id=id, name=name, hp=hp, max_hp=max_hp, hand=hand, role=role,
                      is_alive=bool(is_alive), is_ready=bool(is_ready), position=position, weapon=weapon,
                      permanent_effects=permanent_effects)
    return None


def db_add_player(player: Player):
    cursor.execute("""
        INSERT INTO players (id, name, hp, max_hp, role, is_alive, is_ready, position, weapon, permanent_effects)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (player.id, player.name, player.hp, player.max_hp, player.role, int(player.is_alive), int(player.is_ready),
          player.position, player.weapon, str(player.permanent_effects)))  # Store permanent_effects as string
    conn.commit()


def db_update_player(player: Player):
    cursor.execute("""
        UPDATE players SET name=?, hp=?, max_hp=?, role=?, is_alive=?, is_ready=?, position=?, weapon=?, permanent_effects=?
        WHERE id=?
    """, (
    player.name, player.hp, player.max_hp, player.role, int(player.is_alive), int(player.is_ready), player.position,
    player.weapon, str(player.permanent_effects), player.id))  # Store as string
    conn.commit()


def db_get_room(room_id: int) -> Optional[GameRoom]:
    cursor.execute("SELECT id, game_started, current_player_id, roles_assigned FROM game_rooms WHERE id = ?",
                   (room_id,))
    row = cursor.fetchone()
    if row:
        id, game_started, current_player_id, roles_assigned = row
        # Fetch players
        cursor.execute(
            "SELECT id FROM players WHERE id IN (SELECT player_id FROM player_hands WHERE player_id IN (SELECT id FROM players WHERE id IN (SELECT player_id FROM player_hands)))",
            (id,))
        player_ids = [row[0] for row in cursor.fetchall()]
        players = {player_id: db_get_player(player_id) for player_id in player_ids if
                   db_get_player(player_id) is not None}

        return GameRoom(id=id, players=players, game_started=bool(game_started),
                        current_player_id=current_player_id, roles_assigned=bool(roles_assigned))
    return None


def db_add_room(room_id: int):
    cursor.execute("INSERT INTO game_rooms (id, game_started, current_player_id, roles_assigned) VALUES (?, ?, ?, ?)",
                   (room_id, 0, None, 0))
    conn.commit()


def db_update_room(room: GameRoom):
    cursor.execute("""
        UPDATE game_rooms SET game_started=?, current_player_id=?, roles_assigned=?
        WHERE id=?
    """, (int(room.game_started), room.current_player_id, int(room.roles_assigned), room.id))
    conn.commit()


def db_add_card_to_player_hand(player_id: int, card_name: str):
    cursor.execute("INSERT INTO player_hands (player_id, card_name) VALUES (?, ?)",
                   (player_id, card_name))
    conn.commit()


def db_remove_card_from_player_hand(player_id: int, card_name: str):
    cursor.execute("DELETE FROM player_hands WHERE player_id=? AND card_name=?",
                   (player_id, card_name))
    conn.commit()


def db_get_deck(room_id: int) -> List[Card]:
    cursor.execute("SELECT card_name FROM deck WHERE room_id = ? ORDER BY position", (room_id,))
    card_names = [row[0] for row in cursor.fetchall()]
    return [db_get_card(card_name) for card_name in card_names if db_get_card(card_name) is not None]


def db_add_card_to_deck(room_id: int, card_name: str, position: int):
    cursor.execute("INSERT INTO deck (room_id, card_name, position) VALUES (?, ?, ?)",
                   (room_id, card_name, position))
    conn.commit()


def db_remove_card_from_deck(room_id: int, card_name: str):
    cursor.execute("DELETE FROM deck WHERE room_id=? AND card_name=?", (room_id, card_name))
    conn.commit()


def db_clear_deck(room_id: int):
    cursor.execute("DELETE FROM deck WHERE room_id=?", (room_id,))
    conn.commit()


def db_get_discard_pile(room_id: int) -> List[Card]:
    cursor.execute("SELECT card_name FROM discard_pile WHERE room_id = ?", (room_id,))
    card_names = [row[0] for row in cursor.fetchall()]
    return [db_get_card(card_name) for card_name in card_names if db_get_card(card_name) is not None]


def db_add_card_to_discard_pile(room_id: int, card_name: str):
    cursor.execute("INSERT INTO discard_pile (room_id, card_name) VALUES (?, ?)",
                   (room_id, card_name))
    conn.commit()


def db_clear_discard_pile(room_id: int):
    cursor.execute("DELETE FROM discard_pile WHERE room_id=?", (room_id,))
    conn.commit()


# Data initialization moved to database
def create_deck():
    suits = ["черви", "бубны", "трефы", "пики"]
    values = list(range(2, 11))

    deck = []

    for suit in suits:
        for value in values:
            card = Card(name=f"{value}_{suit}", suit=suit, value=value)
            db_add_card(card)  # Add to DB
            deck.append(card.name)  # Append the card name
    # Simplified code due the usage of DB
    for _ in range(25):
        db_add_card(Card(name="Бэнг"))
        deck.append("Бэнг")
    for _ in range(15):
        db_add_card(Card(name="Мимо"))
        deck.append("Мимо")
    for _ in range(10):
        db_add_card(Card(name="Пиво"))
        deck.append("Пиво")
    for _ in range(2):
        db_add_card(Card(name="Дилижанс"))
        deck.append("Дилижанс")
    for _ in range(2):
        db_add_card(Card(name="Уэллс Фарго"))
        deck.append("Уэллс Фарго")
    for _ in range(2):
        db_add_card(Card(name="Магазин"))
        deck.append("Магазин")
    for _ in range(3):
        db_add_card(Card(name="Паника"))
        deck.append("Паника")
    for _ in range(3):
        db_add_card(Card(name="Красотка"))
        deck.append("Красотка")
    for _ in range(1):
        db_add_card(Card(name="Гатлинг"))
        deck.append("Гатлинг")
    for _ in range(3):
        db_add_card(Card(name="Дуэль"))
        deck.append("Дуэль")

    db_add_card(Card(name="Скофилд"))  # weapon
    deck.append("Скофилд")
    db_add_card(Card(name="Бочка", suit="черви", value=None))  # TODO
    deck.append("Бочка")
    db_add_card(Card(name="Тюрьма"))  # TODO
    deck.append("Тюрьма")
    db_add_card(Card(name="Динамит"))  # TODO
    deck.append("Динамит")
    db_add_card(Card(name="Мустанг"))  # TODO
    deck.append("Мустанг")
    db_add_card(Card(name="Прицел"))  # TODO
    deck.append("Прицел")

    random.shuffle(deck)
    return deck


# API endpoints
@app.post("/create_room/{room_id}")
def create_room(room_id: int):
    if db_get_room(room_id):
        raise HTTPException(status_code=400, detail="Комната уже существует")

    db_add_room(room_id)
    return {"message": f"Комната {room_id} создана"}


@app.post("/add_player/{room_id}/{player_name}")
def add_player(room_id: int, player_name: str):
    room = db_get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Комната не найдена")

    new_id = len(room.players) + 1
    position = new_id - 1

    player = Player(id=new_id, name=player_name, hp=4, max_hp=5, hand=[], role=None, is_alive=True, is_ready=False,
                    position=position, weapon="Кольт", permanent_effects=[])  # Removed hand assignment
    db_add_player(player)

    # Update the player within the room.  This is necessary to reflect the changes.
    room = db_get_room(room_id)  # Re-fetch the room

    return {"message": f"Игрок {player_name} добавлен в комнату {room_id}"}


@app.post("/ready/{room_id}/{player_id}")
def set_ready(room_id: int, player_id: int):
    player = db_get_player(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Игрок не найден")

    player.is_ready = True
    db_update_player(player)
    return {"message": f"Игрок {player_id} готов"}


@app.post("/start_game/{room_id}")
def start_game(room_id: int):
    room = db_get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    players = {p_id: db_get_player(p_id) for p_id in room.players}

    if len(players) < 4:
        raise HTTPException(status_code=400, detail="Недостаточно игроков для начала игры")
    if any(not p.is_ready for p in players.values()):
        raise HTTPException(status_code=400, detail="Не все игроки готовы")

    num_players = len(players)

    if num_players not in [4, 5, 6, 7]:
        raise HTTPException(
            status_code=400, detail="Поддерживаются только игры от 4 до 7 игроков"
        )

    roles = assign_roles(num_players)

    player_list = list(players.values())
    for i, role in enumerate(roles):
        player = player_list[i]
        player.role = role
        db_update_player(player)

    deck = create_deck()
    db_clear_deck(room_id)  # clear the deck
    # Initialize the deck in the database
    for i, card_name in enumerate(deck):
        db_add_card_to_deck(room_id, card_name, i)

    # Раздача карт (по 4 карты каждому игроку)
    for player in players.values():
        # Clear player hands
        clear_player_hand(player)  # clear hand
        draw_cards(player, room, 4)

    room.game_started = True
    room.current_player_id = next(iter(players.keys()))  # Первый игрок
    db_update_room(room)

    return {"message": "Игра началась", "players": [
        {"id": p.id, "name": p.name, "role": p.role} for p in players.values()
    ]}


# Helper Functions

def assign_roles(num_players: int) -> List[str]:
    """Assign roles for a game based on the number of players."""
    if num_players == 4:
        roles = ["шериф", "бандит", "бандит", "ренегат"]
    elif num_players == 5:
        roles = ["шериф", "помощник", "бандит", "бандит", "ренегат"]
    elif num_players == 6:
        roles = ["шериф", "помощник", "помощник", "бандит", "бандит", "ренегат"]
    elif num_players == 7:
        roles = ["шериф", "помощник", "помощник", "бандит", "бандит", "ренегат", "ренегат"]
    else:
        raise ValueError("Unsupported number of players")
    random.shuffle(roles)
    return roles


def draw_cards(player: Player, room: GameRoom, num: int):
    """Draw a specified number of cards from the deck and add them to the player's hand."""
    for _ in range(num):
        card = draw_card(room)  # Use the draw_card() function from database

        if card:
            player.hand.append(card)
            db_update_player(player)  # update player

        else:
            reshuffle_discard_pile(room)

            card = draw_card(room)
            if card:
                player.hand.append(card)
                db_update_player(player)
            else:
                return


def clear_player_hand(player: Player):
    cursor.execute("DELETE FROM player_hands WHERE player_id=?", (player.id,))
    conn.commit()


def reshuffle_discard_pile(room: GameRoom):
    """Reshuffle discard pile into the deck"""
    discard_pile = db_get_discard_pile(room.id)
    if discard_pile:
        random.shuffle(discard_pile)

        db_clear_deck(room.id)  # Clear existing deck
        db_clear_discard_pile(room.id)  # Clear discard pile

        for i, card in enumerate(discard_pile):
            db_add_card_to_deck(room.id, card.name, i)  # Add to the new deck


# Gameplay actions
class PlayerAction(BaseModel):
    player_id: int
    action: str  # "play_card", "pass", "shoot", "use_card"
    card_name: str = None
    target_player_id: Optional[int] = None


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/room/{room_id}")
def get_room_state(room_id: int):
    room = db_get_room(room_id)
    if not room:
        return {"error": "Комната не найдена"}

    players_info = []

    players = {p_id: db_get_player(p_id) for p_id in room.players}

    for p in players.values():
        players_info.append(
            {
                "id": p.id,
                "name": p.name,
                "hp": p.hp,
                "max_hp": p.max_hp,
                "hand": [card.name for card in p.hand],
                "role": p.role if p.role == "шериф" else None,
                "is_alive": p.is_alive,
                "is_ready": p.is_ready,
                "weapon": p.weapon,
                "permanent_effects": p.permanent_effects,
            }
        )

    deck = db_get_deck(room_id)

    return {
        "players": players_info,
        "game_started": room.game_started,
        "current_player": room.current_player_id,
        "deck_count": len(deck),
    }


@app.post("/player_action/{room_id}")
def player_action(room_id: int, action_data: PlayerAction):
    room = db_get_room(room_id)

    if not room or not room.game_started:
        raise HTTPException(status_code=400, detail="Игра не началась или комната не найдена")

    player = get_player_by_id(room, action_data.player_id)

    if not player or not player.is_alive:
        raise HTTPException(status_code=404, detail="Игрок не найден или мертв")

    current_player = get_current_player(room)

    if current_player.id != player.id:
        raise HTTPException(status_code=403, detail="Не ваш ход")

    try:
        if action_data.action == "play_card":
            return handle_play_card(room, player, action_data.card_name, action_data.target_player_id)
        elif action_data.action == "pass":
            pass_turn(room)
            return {"status": "ход передан"}
        elif action_data.action == "shoot":
            return handle_shoot(room, player, action_data.target_player_id)
        else:
            raise HTTPException(status_code=400, detail="Неизвестное действие")

    except HTTPException as e:
        raise e  # re-raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Helper Functions
def get_player_by_id(room: GameRoom, player_id: int) -> Player:
    player = db_get_player(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Игрок не найден")
    return player


def get_current_player(room: GameRoom) -> Player:
    player = db_get_player(room.current_player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Текущий игрок не найден")
    return player


def calculate_distance(p1_id: int, p2_id: int, room: GameRoom) -> int:
    """Расчет расстояния между двумя игроками по кругу"""
    p1 = get_player_by_id(room, p1_id)
    p2 = get_player_by_id(room, p2_id)
    if not p1 or not p2:
        raise HTTPException(status_code=404, detail="Игрок не найден")

    if p1_id == p2_id:
        return 0

    num_players = len(room.players)
    distance = abs(p1.position - p2.position)
    distance = min(distance, num_players - distance)

    # Учитываем эффекты мустанга
    if has_permanent_effect(p2, "Мустанг"):
        distance += 1

    return distance


def get_weapon_range(player: Player) -> int:
    weapon_range = WEAPONS.get(player.weapon, 1)  # Default to Colt (range 1)
    if has_permanent_effect(player, "Прицел"):
        weapon_range += 1
    return weapon_range


def has_permanent_effect(player: Player, effect_name: str) -> bool:
    return effect_name in player.permanent_effects


def add_permanent_effect(player: Player, effect_name: str):
    if effect_name not in player.permanent_effects:
        player.permanent_effects.append(effect_name)


def remove_permanent_effect(player: Player, effect_name: str):
    if effect_name in player.permanent_effects:
        player.permanent_effects.remove(effect_name)


def handle_shoot(room: GameRoom, shooter: Player, target_player_id: int):
    """Handles the shoot action"""
    target = get_player_by_id(room, target_player_id)

    distance = calculate_distance(shooter.id, target.id, room)
    weapon_range = get_weapon_range(shooter)

    if distance > weapon_range:
        raise HTTPException(status_code=400, detail="Цель вне диапазона выстрела")

    # Find the "Бэнг" card in the shooter's hand
    bang_card = next((card for card in shooter.hand if card.name == "Бэнг"), None)

    if not bang_card:
        raise HTTPException(status_code=400, detail="Нет карты 'Бэнг' в руке")

    # Remove the "Бэнг" card from the shooter's hand and discard it
    shooter.hand.remove(bang_card)
    db_remove_card_from_player_hand(shooter.id, bang_card.name)

    db_add_card_to_discard_pile(room.id, bang_card.name)

    # The target player must now defend
    return handle_defend(room, target, shooter)  # Pass the shooter as well
    # Remove maximum hand
    reset_hand_size(shooter)


def handle_defend(room: GameRoom, target: Player, shooter: Player):
    """Handles the defending action"""
    # Check for "Мимо" card
    mimo_card = next((card for card in target.hand if card.name == "Мимо"), None)
    if mimo_card:
        # Remove mimo
        target.hand.remove(mimo_card)
        db_remove_card_from_player_hand(target.id, mimo_card.name)
        db_add_card_to_discard_pile(room.id, mimo_card.name)
        return {"status": f"Игрок {target.name} уклонился"}

    # Check for "Бочка" effect if no "Mimo" card is available
    if has_permanent_effect(target, "Бочка"):
        remove_permanent_effect(target, "Бочка")  # "Бочка" is a one-time use effect
        card = draw_card(room)  # Drawing card to check effect

        if card and card.suit == "черви":
            db_add_card_to_discard_pile(room.id, card.name)  # Discard the drawn card
            return {"status": f"Игрок {target.name} уклонился с помощью бочки!"}
        elif card:
            db_add_card_to_discard_pile(room.id, card.name)  # Discard the drawn card if it's not черви

    # If no "Mimo" card and no "Бочка" effect, the player takes damage
    target.hp -= 1
    db_update_player(target)

    check_player_death(target, room)

    # You can also implement additional logic to handle specific cases
    if target.hp <= 0:
        return {"status": f"Игрок {target.name} убит"}

    return {"status": f"Игрок {target.name} получил выстрел"}  # No defending card


def handle_duel(room: GameRoom, p1: Player, p2: Player):
    """Handles duel action"""

    def duel_round(attacker: Player, defender: Player) -> bool:
        """returns True if the duel can continue, False otherwise"""
        bang_card = next((card for card in attacker.hand if card.name == "Бэнг"), None)

        if bang_card:
            attacker.hand.remove(bang_card)
            db_remove_card_from_player_hand(attacker.id, bang_card.name)
            db_add_card_to_discard_pile(room.id, bang_card.name)
        else:
            # Attacker cannot answer -> he lose
            defender.hp -= 1
            db_update_player(defender)

            check_player_death(defender, room)
            return False  # end duel

        return True  # Continue duel

    # Duel rounds
    current_attacker = p2
    current_defender = p1  # Player

    while True:
        if not duel_round(current_attacker, current_defender):
            break

        # Swap players
        current_attacker, current_defender = current_defender, current_attacker

        # After a shoot
        if not duel_round(current_attacker, current_defender):
            break

    # After duel
    return {"status": "Duel has been completed"}


def handle_play_card(room: GameRoom, player: Player, card_name: str, target_player_id: Optional[int] = None):
    """Handles the playing of a card"""

    card = next((card for card in player.hand if card.name == card_name), None)
    if not card:
        raise HTTPException(status_code=400, detail="Карта не найдена в руке")

    player.hand.remove(card)
    db_remove_card_from_player_hand(player.id, card.name)
    db_add_card_to_discard_pile(room.id, card.name)

    if card.name == "Пиво":
        handle_pivo(player, room)
        reset_hand_size(player)
        return {"status": "Пиво использовано", "hp": player.hp}

    elif card.name == "Дилижанс":
        draw_cards(player, room, 2)
        reset_hand_size(player)
        return {"status": "Дилижанс использован"}

    elif card.name == "Уэллс Фарго":
        draw_cards(player, room, 3)
        reset_hand_size(player)
        return {"status": "Уэллс Фарго использован"}

    elif card.name == "Магазин":
        handle_magazin(player, room)
        reset_hand_size(player)
        return {"status": "Магазин использован"}

    elif card.name == "Гатлинг":
        handle_gatling(room, player)
        reset_hand_size(player)
        return {"status": "Гатлинг использован"}

    elif card.name == "Дуэль":
        if target_player_id == None:
            raise HTTPException(status_code=400, detail="Не указан целевой игрок")
        target = get_player_by_id(room, target_player_id)
        return handle_duel(room, player, target)

    elif card.name == "Тюрьма":
        if target_player_id == None:
            raise HTTPException(status_code=400, detail="Не указан целевой игрок")

        handle_turma(player, get_player_by_id(room, target_player_id))
        reset_hand_size(player)
        return {"status": "Тюрьма применена на целевого игрока"}

    elif card.name == "Динамит":
        handle_dynamite(room)
        reset_hand_size(player)
        return {"status": "Динамит применен"}

    elif card.name == "Бочка":
        handle_bocka(player)
        reset_hand_size(player)
        return {"status": "Бочка применена"}

    elif card.name == "Мустанг":
        handle_pivo(player, room)
        reset_hand_size(player)
        add_permanent_effect(player, card.name)
        return {"status": "Мустанг был применен"}
    elif card.name == "Прицел":
        handle_pivo(player, room)
        reset_hand_size(player)
        add_permanent_effect(player, card.name)
        return {"status": "Прицел был применен"}
    elif card.name == "Скофилд":
        handle_pivo(player, room)
        reset_hand_size(player)
        add_permanent_effect(player, card.name)
        return {"status": "Скофилд был применен"}
    elif card.name == "Паника":
        handle_panic(player, room)
        reset_hand_size(player)
        return {"status": "Паника применена"}
    elif card.name == "Красотка":
        handle_krassotka(player, room)
        reset_hand_size(player)
        return {"status": "Красотка применена"}

    reset_hand_size(player)
    return {"status": f"Карта '{card_name}' сыгра