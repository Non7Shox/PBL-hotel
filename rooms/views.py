from django.shortcuts import render, get_object_or_404
from django.db.models import Min
from .models import Room, Floor

# 1. Главная страница отеля с описанием и кнопкой перехода к этажам
def room_list(request):
    total_rooms = Room.objects.count()
    total_floors = Floor.objects.count()
    min_price = Room.objects.aggregate(Min('price_per_night'))['price_per_night__min'] or 0

    context = {
        'total_rooms': total_rooms,
        'total_floors': total_floors,
        'min_price': min_price,
    }
    return render(request, 'rooms/room_list.html', context)


# 2. Интерактивная схема этажей с кнопкой переключения слева
def hotel_floors(request):
    floors = Floor.objects.prefetch_related('rooms').all()
    return render(request, 'rooms/hotel_floors.html', {'floors': floors})


# 3. Детальная страница комнаты с 3D-туром
def room_detail(request, pk):
    room = get_object_or_404(Room, pk=pk)
    return render(request, 'rooms/room_detail.html', {'room': room})