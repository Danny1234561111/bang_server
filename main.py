from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
import random

app = FastAPI()

# Модели данных

class Card(BaseModel):
    name: str
    suit: Optional[str] = None  # Масть (черви, пики и т.д.)
    value: Optional[int] = None  # Номинал (цифра)


class Player(BaseModel):
    id: int
    name: str
    hp: int = 4
    max_hp: int = 5
    hand: List[Card] = []
    role: Optional[str] = None  # 'шериф', 'бандит', 'ренегат', 'помощник'
    is_alive: bool = True
    is_ready: bool = False
    position: int = 0  # для определения расстояний
    weapon: str = "Кольт"  # Оружие (Кольт, Скофилд и т.д.)
    permanent_effects: List[str] = []  # Постоянные эффекты (Мустанг, Прицел и т.п.)


class GameRoom(BaseModel):
    id: int
    players: Dict[int, Player] = {}
    deck: List[Card] = []
    discard_pile: List[Card] = []
    game_started: bool = False
    current_player_id: Optional[int] = None
    roles_assigned: bool = False

rooms: Dict[int, GameRoom] = {}

# Константы

WEAPONS = {
    "Кольт": 1,
    "Скофилд": 2,
    "Ремингтон": 3,
    "Карабин": 4,
    "Винчестер": 5,
    "Воканчик": 1,
}

# Создание колоды карт
def create_deck():
    suits = ["черви", "бубны", "трефы", "пики"]
    values = list(range(2, 11))  # карты от 2 до 10

    deck = []

    # Добавляем обычные карты (масть + значение)
    for suit in suits:
        for value in values:
            deck.append(Card(name=f"{value}_{suit}", suit=suit, value=value))

    # Бэнг (выстрел) - 25 карт
    for _ in range(25):
        deck.append(Card(name="Бэнг"))

    # Мимо (уворот) - 15 карт
    for _ in range(15):
        deck.append(Card(name="Мимо"))

    # Пиво (восстановление здоровья) - 10 карт
    for _ in range(10):
        deck.append(Card(name="Пиво"))

    # Дилижанс (взять две карты из колоды) - 2 карты
    for _ in range(2):
        deck.append(Card(name="Дилижанс"))

    # Уэллс Фарго (взять три карты из колоды)
    for _ in range(2):
        deck.append(Card(name="Уэллс Фарго"))

    # Магазин (карты для всех игроков) - 2 карты
    for _ in range(2):
        deck.append(Card(name="Магазин"))

    # Паника (забрать карту другого игрока) - 3 карты
    for _ in range(3):
        deck.append(Card(name="Паника"))

    # Красотка (сбросить карту другого игрока) - 3 карты
    for _ in range(3):
        deck.append(Card(name="Красотка"))

    # Гатлинг (выстрел по всем) - 1 карта
    for _ in range(1):
        deck.append(Card(name="Гатлинг"))

    # Дуэль (вызов на дуэль) - 3 карты
    for _ in range(3):
        deck.append(Card(name="Дуэль"))

    # Оружие (пока добавим только Скофилд для примера)
    deck.append(Card(name="Скофилд")) #TODO исправить как константы

    # Бочка
    deck.append(Card(name="Бочка", suit="черви", value=None)) #TODO исправить

    # Тюрьма
    deck.append(Card(name="Тюрьма")) #TODO исправить

    # Динамит
    deck.append(Card(name="Динамит")) #TODO исправить

    #Мустанг
    deck.append(Card(name="Мустанг")) #TODO исправить

    #Прицел
    deck.append(Card(name="Прицел")) #TODO исправить

    random.shuffle(deck)
    return deck

# API endpoints

@app.post("/create_room/{room_id}")
def create_room(room_id: int):
    if room_id in rooms:
        raise HTTPException(status_code=400, detail="Комната уже существует")

    rooms[room_id] = GameRoom(id=room_id)
    return {"message": f"Комната {room_id} создана"}

@app.post("/add_player/{room_id}/{player_name}")
def add_player(room_id: int, player_name: str):
    room = rooms.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Комната не найдена")

    new_id = len(room.players) + 1
    position = new_id - 1

    player = Player(id=new_id, name=player_name, position=position)
    room.players[new_id] = player
    return {"message": f"Игрок {player_name} добавлен в комнату {room_id}"}

@app.post("/ready/{room_id}/{player_id}")
def set_ready(room_id: int, player_id: int):
    room = rooms.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    player = room.players.get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Игрок не найден")

    player.is_ready = True
    return {"message": f"Игрок {player_id} готов"}

@app.post("/start_game/{room_id}")
def start_game(room_id: int):
    room = rooms.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Комната не найдена")

    if len(room.players) < 4:
        raise HTTPException(status_code=400, detail="Недостаточно игроков для начала игры")
    if any(not p.is_ready for p in room.players.values()):
        raise HTTPException(status_code=400, detail="Не все игроки готовы")

    num_players = len(room.players)

    if num_players not in [4, 5, 6, 7]:
        raise HTTPException(
            status_code=400, detail="Поддерживаются только игры от 4 до 7 игроков"
        )

    roles = assign_roles(num_players)

    for player, role in zip(room.players.values(), roles):
        player.role = role

    room.deck = create_deck()

    # Раздача карт (по 4 карты каждому игроку)
    for player in room.players.values():
        player.hand = []
        draw_cards(player, room, 4)

    room.game_started = True
    room.current_player_id = next(iter(room.players.keys()))  # Первый игрок
    return {"message": "Игра началась", "players": [
        {"id": p.id, "name": p.name, "role": p.role} for p in room.players.values()
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
        raise ValueError("Unsupported number of players")  # should not happen, handled before
    random.shuffle(roles)
    return roles

def draw_cards(player: Player, room: GameRoom, num: int):
    """Draw a specified number of cards from the deck and add them to the player's hand."""
    for _ in range(num):
        if room.deck:
            card = room.deck.pop(0)  # get first from the deck
            player.hand.append(card)
        else:
            # reshuffle
            reshuffle_discard_pile(room)
            if room.deck:
                card = room.deck.pop(0)
                player.hand.append(card)
            else:
                return # no cards to add anymore.

def reshuffle_discard_pile(room : GameRoom):
    """Reshuffle discard pile into the deck"""
    if room.discard_pile:
      random.shuffle(room.discard_pile)
      room.deck = room.discard_pile
      room.discard_pile = []

#Gameplay actions

class PlayerAction(BaseModel):
    player_id: int
    action: str  # "play_card", "pass", "shoot", "use_card"
    card_name: str = None
    target_player_id: Optional[int] = None

@app.get("/room/{room_id}")
def get_room_state(room_id: int):
    room = rooms.get(room_id)
    if not room:
        return {"error": "Комната не найдена"}

    players_info = []
    for p in room.players.values():
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
    return {
        "players": players_info,
        "game_started": room.game_started,
        "current_player": room.current_player_id,
        "deck_count": len(room.deck),
    }

@app.post("/player_action/{room_id}")
def player_action(room_id: int, action_data: PlayerAction):
    room = rooms.get(room_id)
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
        raise e # re-raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_player_by_id(room: GameRoom, player_id: int) -> Player:
    player = room.players.get(player_id)
    if not player:
         raise HTTPException(status_code=404, detail="Игрок не найден")
    return player

def get_current_player(room: GameRoom) -> Player:
    if not room.current_player_id:
        raise HTTPException(status_code=500, detail="Текущий игрок не определен")

    player = room.players.get(room.current_player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Текущий игрок не найден")
    return player

def calculate_distance(p1_id: int, p2_id: int, room: GameRoom) -> int:
    """Расчет расстояния между двумя игроками по кругу"""
    if p1_id == p2_id:
        return 0

    p1 = get_player_by_id(room, p1_id)
    p2 = get_player_by_id(room, p2_id)

    num_players = len(room.players)
    distance = abs(p1.position - p2.position)
    distance = min(distance, num_players - distance)

    #Учитываем эффекты мустанга
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
    room.discard_pile.append(bang_card)

    # The target player must now defend
    return handle_defend(room, target, shooter)  # Pass the shooter as well
    #Remove maximum hand
    reset_hand_size(shooter)

def handle_defend(room: GameRoom, target: Player, shooter: Player):
    """Handles the defending action"""
    #Check for "Мимо" card
    mimo_card = next((card for card in target.hand if card.name == "Мимо"), None)
    if mimo_card:
        #Remove mimo
        target.hand.remove(mimo_card)
        room.discard_pile.append(mimo_card)
        return {"status": f"Игрок {target.name} уклонился"}

    # Check for "Бочка" effect if no "Mimo" card is available
    if has_permanent_effect(target, "Бочка"):
        remove_permanent_effect(target, "Бочка")  # "Бочка" is a one-time use effect
        card = draw_card(room)  # Drawing card to check effect

        if card and card.suit == "черви":
            room.discard_pile.append(card)  # Discard the drawn card
            return {"status": f"Игрок {target.name} уклонился с помощью бочки!"}
        elif card:
            room.discard_pile.append(card)  # Discard the drawn card if it's not черви

    # If no "Mimo" card and no "Бочка" effect, the player takes damage
    target.hp -= 1
    check_player_death(target, room)

    # You can also implement additional logic to handle specific cases
    if target.hp <= 0:
        return {"status": f"Игрок {target.name} убит"}

    return {"status": f"Игрок {target.name} получил выстрел"} #No defending card

def handle_duel(room: GameRoom, p1:Player, p2: Player):
    """Handles duel action"""

    def duel_round(attacker: Player, defender: Player) -> bool:
      """returns True if the duel can continue, False otherwise"""
      bang_card = next((card for card in attacker.hand if card.name == "Бэнг"), None)

      if bang_card:
          attacker.hand.remove(bang_card)
          room.discard_pile.append(bang_card)
      else:
          #Attacker cannot answer -> he lose
          defender.hp -= 1
          check_player_death(defender, room)
          return False # end duel

      return True #Continue duel

    #Duel rounds
    current_attacker = p2
    current_defender = p1 #Player

    while True:
      if not duel_round(current_attacker, current_defender):
        break

      #Swap players
      current_attacker, current_defender = current_defender, current_attacker

      #After a shoot
      if not duel_round(current_attacker, current_defender):
        break

    #After duel
    return {"status" : "Duel has been completed"}

def handle_play_card(room: GameRoom, player: Player, card_name: str, target_player_id : Optional[int] = None):
    """Handles the playing of a card"""
    card = next((card for card in player.hand if card.name == card_name), None)
    if not card:
        raise HTTPException(status_code=400, detail="Карта не найдена в руке")

    player.hand.remove(card)
    room.discard_pile.append(card)

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
        return {"status" : "Уэллс Фарго использован"}

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
        return {"status" : "Тюрьма применена на целевого игрока"}

    elif card.name == "Динамит":
         handle_dynamite(room)
         reset_hand_size(player)
         return {"status" : "Динамит применен"}

    elif card.name == "Бочка":
         handle_bocka(player)
         reset_hand_size(player)
         return {"status" : "Бочка применена"}

    elif card.name == "Мустанг":
         handle_pivo(player, room)
         reset_hand_size(player)
         add_permanent_effect(player, card.name)
         return {"status" : "Мустанг был применен"}
    elif card.name == "Прицел":
         handle_pivo(player, room)
         reset_hand_size(player)
         add_permanent_effect(player, card.name)
         return {"status" : "Прицел был применен"}
    elif card.name == "Скофилд":
         handle_pivo(player, room)
         reset_hand_size(player)
         add_permanent_effect(player, card.name)
         return {"status" : "Скофилд был применен"}
    elif card.name == "Паника":
          handle_panic(player, room)
          reset_hand_size(player)
          return {"status" : "Паника применена"}
    elif card.name == "Красотка":
         handle_krassotka(player, room)
         reset_hand_size(player)
         return {"status" : "Красотка применена"}


    reset_hand_size(player)
    return {"status": f"Карта '{card_name}' сыграна"}

def handle_gatling(room: GameRoom, p1: Player):
    """Handles the Gatling card"""
    #Fire at everyone who can be defended
    for p2Id, p2 in room.players.items():
        #Avoid shooting yourself
        if p2Id != p1.id:
            handle_defend(room, p2, p1)

def handle_magazin(player: Player, room: GameRoom):
     for _ in range(len(room.players.values())): #number of players
            if room.deck:
                card = room.deck.pop(0)
                player.hand.append(card) #add to current player hand
            else:
                reshuffle_discard_pile(room)
                if room.deck:
                    card = room.deck.pop(0)
                    player.hand.append(card) #add to current player hand
                else:
                    break

def handle_dynamite(room: GameRoom):
    process_dynamite_trigger(room)

def handle_bocka(player: Player):
  add_permanent_effect(player, "Бочка")

def check_turma(player: Player, room: GameRoom) -> bool:
    card = draw_card(room)
    if card and card.suit == "черви":
        remove_permanent_effect(player, "Тюрьма")
        room.discard_pile.append(card)
        return True  # Освобожден
    else:
        if card:
            room.discard_pile.append(card)
        return False

def handle_krassotka(player: Player, room: GameRoom):
  """Handles Panika effect action, take a random card"""
  if not room.current_player_id:
        raise HTTPException(status_code=500, detail="Текущий игрок не определен")

  for p2Id, p2 in room.players.items():
        if p2Id != room.current_player_id and p2.hand:
           #Remove a random card from target
           card_to_steal_index = random.randint(0, len(p2.hand) - 1)
           card_to_steal = p2.hand.pop(card_to_steal_index)
           #Add card
           player.hand.append(card_to_steal)
           room.discard_pile.append(card_to_steal) #remove from discard pile

def handle_panic(player: Player, room: GameRoom):
  """Handles Panika effect action, take a random card"""
  if not room.current_player_id:
        raise HTTPException(status_code=500, detail="Текущий игрок не определен")

  for p2Id, p2 in room.players.items():
        if p2Id != room.current_player_id and p2.hand:
           #Remove a random card from target
           card_to_steal_index = random.randint(0, len(p2.hand) - 1)
           card_to_steal = p2.hand.pop(card_to_steal_index)
           #Add card
           player.hand.append(card_to_steal)

def handle_pivo(player: Player, room: GameRoom):
    if player.hp < player.max_hp:
        player.hp += 1

def check_player_death(player: Player, room: GameRoom):
    if player.hp <= 0:
        player.is_alive = False

def pass_turn(room: GameRoom):
    """Advances the game turn to the next player."""
    advance_turn(room)

def advance_turn(room: GameRoom):
    players = list(room.players.values())
    current_idx = next((i for i, p in enumerate(players) if p.id == room.current_player_id), 0)
    total = len(players)
    for i in range(1, total + 1):
        next_idx = (current_idx + i) % total
        next_player = players[next_idx]
        if next_player.is_alive:
            room.current_player_id = next_player.id
            break

def draw_card(room : GameRoom)-> Card:
    if  room.deck:
       return room.deck.pop(0)
    else:
        reshuffle_discard_pile(room)
        if  room.deck:
            return room.deck.pop(0)
        else:
            return None #no card at all!

def process_dynamite_trigger(room: GameRoom):
    for p in list(room.players.values()):
        if has_permanent_effect(p, 'Динамит'):
            card = draw_card(room)
            if not card:
                continue
            if card.suit == 'пики' and 2 <= card.value <= 9:
                # Взрыв! Игрок теряет 3 хп и динамит снимается.
                p.hp -= 3
                remove_permanent_effect(p, 'Динамит')
                room.discard_pile.append(card)
                check_player_death(p, room)
            else:
                add_permanent_effect(p, 'Динамит')
                room.discard_pile.append(card)

def get_next_player(room: GameRoom, current_player_id: int) -> Optional[Player]:
  """Get next player in a circle"""
  players = list(room.players.values())
  current_idx = next((i for i, p in enumerate(players) if p.id == current_player_id), 0)
  total = len(players)
  for i in range(1, total + 1):
    next_idx = (current_idx + i) % total
    next_player = players[next_idx]
    if next_player.is_alive:
      return next_player

  return None #no next player

def reset_hand_size(player : Player):
   while len(player.hand) > player.hp:
        card = player.hand.pop() #reset the size
        #Discard ?
