"""Подбор номера: прозрачная оценка по правилам, без внешних сервисов."""

# веса: (пожелания, цена, вместимость)
WEIGHTS = {
    'balance': (50, 30, 20),
    'price': (30, 55, 15),
    'comfort': (65, 10, 25),
}


def score_room(room, *, guests, budget, wishes, priority, max_room_price):
    """Возвращает (процент совпадения, причины, чего не хватает)."""
    w_wish, w_price, w_space = WEIGHTS[priority]
    reasons, missing = [], []

    have = {amenity.pk for amenity in room.amenities.all()}
    matched = [wish for wish in wishes if wish.pk in have]
    missing += [wish.name for wish in wishes if wish.pk not in have]
    if wishes:
        wish_score = len(matched) / len(wishes)
        if matched:
            reasons.append("Есть: " + ", ".join(w.name for w in matched))
    else:
        # без пожеланий комфорт оцениваем по числу удобств
        wish_score = min(len(have) / 6, 1)

    price = float(room.price_per_night)
    if budget is not None and price > float(budget):
        over = price - float(budget)
        price_score = max(0.0, 1 - over / max(float(budget), 1) * 2)
        missing.append(f"дороже бюджета на ${over:.0f}")
    else:
        # чем дешевле относительно самого дорогого номера, тем выше оценка
        price_score = 1 - 0.5 * price / max(max_room_price, 1)
        if budget is not None:
            reasons.append("Укладывается в бюджет")

    spare = room.capacity - guests
    space_score = {0: 1.0, 1: 0.85}.get(spare, 0.65)
    if spare == 0:
        reasons.append("Вместимость точно под вашу компанию")
    else:
        reasons.append(f"Просторно: рассчитан на {room.capacity} гостей")

    total = w_wish * wish_score + w_price * price_score + w_space * space_score
    return round(total), reasons, missing
