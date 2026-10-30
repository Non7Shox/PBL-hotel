"""Генератор простой 3D модели гостиничного номера в формате glTF (.glb).

Модель собирается из параллелепипедов и цилиндров: стены с окном, кровать,
тумбочки с лампами, шкаф, стол со стулом, телевизор, ковёр. Передней стены и
потолка нет — номер виден в разрезе, как кукольный домик. Единицы — метры,
ось Y смотрит вверх, начало координат в центре пола.

Внешних зависимостей нет: бинарный буфер glTF упаковывается через struct.
"""
import json
import math
import struct
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- палитры

PALETTES = [
    {   # тёплая: светлое дерево, бежевый текстиль
        'wall': '#ebe4d8', 'floor': '#9c7752', 'baseboard': '#f4efe6',
        'wood': '#7a5a40', 'headboard': '#6b4f3a', 'blanket': '#cbb89c',
        'runner': '#8a6a45', 'linen': '#f7f5f0', 'curtain': '#d9ccb5',
        'rug': '#b7a387', 'chair': '#5c4636', 'metal': '#2b2b2b',
    },
    {   # спокойная: серо-голубой, тёмное дерево
        'wall': '#e0e1dd', 'floor': '#7f6b58', 'baseboard': '#f0f0ec',
        'wood': '#4b4f54', 'headboard': '#3e4347', 'blanket': '#5d6873',
        'runner': '#323a41', 'linen': '#f6f6f3', 'curtain': '#a0a8ad',
        'rug': '#8e959a', 'chair': '#3a3e42', 'metal': '#1f1f1f',
    },
    {   # зелёная: оливковые акценты
        'wall': '#e6e6de', 'floor': '#8f7458', 'baseboard': '#f3f2ec',
        'wood': '#6e5a45', 'headboard': '#4f5b48', 'blanket': '#7d8a6c',
        'runner': '#46523f', 'linen': '#f7f6f1', 'curtain': '#c4c6b4',
        'rug': '#a6a48f', 'chair': '#4a4438', 'metal': '#262626',
    },
]


def _rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    # glTF ждёт линейные значения; переводим из sRGB
    out = []
    for i in (0, 2, 4):
        c = int(hex_color[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out


# --------------------------------------------------------------------------- геометрия

@dataclass
class _Mesh:
    positions: list = field(default_factory=list)
    normals: list = field(default_factory=list)
    indices: list = field(default_factory=list)

    def add_quad(self, a, b, c, d, n):
        base = len(self.positions)
        self.positions += [a, b, c, d]
        self.normals += [n, n, n, n]
        self.indices += [base, base + 1, base + 2, base, base + 2, base + 3]


class SceneBuilder:
    """Копит геометрию по материалам и выдаёт готовый .glb."""

    def __init__(self, mirror=False):
        self.mirror = mirror
        self.materials = {}   # имя -> описание материала glTF
        self.meshes = {}      # имя материала -> _Mesh

    def material(self, name, color, roughness=0.8, metallic=0.0, alpha=1.0, emissive=None):
        if name not in self.materials:
            pbr = {
                'baseColorFactor': _rgb(color) + [alpha],
                'metallicFactor': metallic,
                'roughnessFactor': roughness,
            }
            mat = {'name': name, 'pbrMetallicRoughness': pbr}
            if alpha < 1:
                mat['alphaMode'] = 'BLEND'
                mat['doubleSided'] = True
            if emissive:
                mat['emissiveFactor'] = _rgb(emissive)
            self.materials[name] = mat
            self.meshes[name] = _Mesh()
        return name

    def _x(self, x):
        return -x if self.mirror else x

    def box(self, mat, center, size):
        """Параллелепипед по центру и размерам (x, y, z)."""
        cx, cy, cz = center
        cx = self._x(cx)
        sx, sy, sz = (s / 2 for s in size)
        x0, x1, y0, y1, z0, z1 = cx - sx, cx + sx, cy - sy, cy + sy, cz - sz, cz + sz
        m = self.meshes[mat]
        m.add_quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (0, 0, 1))
        m.add_quad((x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (0, 0, -1))
        m.add_quad((x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (1, 0, 0))
        m.add_quad((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0), (-1, 0, 0))
        m.add_quad((x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0), (0, 1, 0))
        m.add_quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (0, -1, 0))

    def cylinder(self, mat, center, radius_bottom, radius_top, height, segments=24):
        """Цилиндр или усечённый конус, стоящий на точке center (низ)."""
        cx, cy, cz = center
        cx = self._x(cx)
        m = self.meshes[mat]
        slope = (radius_bottom - radius_top) / height
        for i in range(segments):
            a0 = 2 * math.pi * i / segments
            a1 = 2 * math.pi * (i + 1) / segments
            am = (a0 + a1) / 2
            n_len = math.sqrt(1 + slope ** 2)
            n = (math.cos(am) / n_len, slope / n_len, math.sin(am) / n_len)
            b0 = (cx + radius_bottom * math.cos(a0), cy, cz + radius_bottom * math.sin(a0))
            b1 = (cx + radius_bottom * math.cos(a1), cy, cz + radius_bottom * math.sin(a1))
            t1 = (cx + radius_top * math.cos(a1), cy + height, cz + radius_top * math.sin(a1))
            t0 = (cx + radius_top * math.cos(a0), cy + height, cz + radius_top * math.sin(a0))
            m.add_quad(b0, t0, t1, b1, n)
            # крышка и дно: треугольники как вырожденные четырёхугольники
            top_c = (cx, cy + height, cz)
            m.add_quad(top_c, t1, t0, t0, (0, 1, 0))
            bot_c = (cx, cy, cz)
            m.add_quad(bot_c, b0, b1, b1, (0, -1, 0))

    # ----------------------------------------------------------------------- экспорт

    def to_glb(self, name='room'):
        buffer = bytearray()
        buffer_views, accessors, meshes, nodes = [], [], [], []

        def add_view(data, target):
            while len(buffer) % 4:
                buffer.append(0)
            offset = len(buffer)
            buffer.extend(data)
            buffer_views.append({'buffer': 0, 'byteOffset': offset, 'byteLength': len(data), 'target': target})
            return len(buffer_views) - 1

        materials = list(self.materials.values())
        for mat_index, (mat_name, mesh) in enumerate(self.meshes.items()):
            if not mesh.indices:
                continue
            pos = b''.join(struct.pack('<3f', *p) for p in mesh.positions)
            nor = b''.join(struct.pack('<3f', *n) for n in mesh.normals)
            idx = b''.join(struct.pack('<I', i) for i in mesh.indices)
            xs, ys, zs = zip(*mesh.positions)

            accessors.append({
                'bufferView': add_view(pos, 34962), 'componentType': 5126,
                'count': len(mesh.positions), 'type': 'VEC3',
                'min': [min(xs), min(ys), min(zs)], 'max': [max(xs), max(ys), max(zs)],
            })
            pos_acc = len(accessors) - 1
            accessors.append({
                'bufferView': add_view(nor, 34962), 'componentType': 5126,
                'count': len(mesh.normals), 'type': 'VEC3',
            })
            nor_acc = len(accessors) - 1
            accessors.append({
                'bufferView': add_view(idx, 34963), 'componentType': 5125,
                'count': len(mesh.indices), 'type': 'SCALAR',
            })
            idx_acc = len(accessors) - 1

            meshes.append({
                'name': mat_name,
                'primitives': [{
                    'attributes': {'POSITION': pos_acc, 'NORMAL': nor_acc},
                    'indices': idx_acc,
                    'material': mat_index,
                }],
            })
            nodes.append({'name': mat_name, 'mesh': len(meshes) - 1})

        while len(buffer) % 4:
            buffer.append(0)

        gltf = {
            'asset': {'version': '2.0', 'generator': 'Aurelio Hotel room generator'},
            'scene': 0,
            'scenes': [{'name': name, 'nodes': list(range(len(nodes)))}],
            'nodes': nodes,
            'meshes': meshes,
            'materials': materials,
            'accessors': accessors,
            'bufferViews': buffer_views,
            'buffers': [{'byteLength': len(buffer)}],
        }
        json_chunk = json.dumps(gltf, separators=(',', ':')).encode('utf-8')
        while len(json_chunk) % 4:
            json_chunk += b' '

        total = 12 + 8 + len(json_chunk) + 8 + len(buffer)
        return b''.join([
            struct.pack('<4sII', b'glTF', 2, total),
            struct.pack('<I4s', len(json_chunk), b'JSON'), json_chunk,
            struct.pack('<I4s', len(buffer), b'BIN\x00'), bytes(buffer),
        ])


# --------------------------------------------------------------------------- номер

def build_room_glb(variant=0, capacity=2, name='room'):
    """Собирает модель номера. variant меняет палитру и зеркалит планировку."""
    pal = PALETTES[variant % len(PALETTES)]
    s = SceneBuilder(mirror=bool(variant % 2))

    W, D, H, T = 4.0, 5.0, 2.7, 0.1   # ширина, глубина, высота, толщина стен
    half_w, half_d = W / 2, D / 2

    wall = s.material('wall', pal['wall'], roughness=0.95)
    floor = s.material('floor', pal['floor'], roughness=0.6)
    base = s.material('baseboard', pal['baseboard'], roughness=0.7)
    wood = s.material('wood', pal['wood'], roughness=0.55)
    head = s.material('headboard', pal['headboard'], roughness=0.9)
    blanket = s.material('blanket', pal['blanket'], roughness=1.0)
    runner = s.material('runner', pal['runner'], roughness=1.0)
    linen = s.material('linen', pal['linen'], roughness=1.0)
    curtain = s.material('curtain', pal['curtain'], roughness=1.0)
    rug = s.material('rug', pal['rug'], roughness=1.0)
    chair = s.material('chair', pal['chair'], roughness=0.8)
    metal = s.material('metal', pal['metal'], roughness=0.35, metallic=0.6)
    screen = s.material('screen', '#111214', roughness=0.2)
    glass = s.material('glass', '#bcd6e6', roughness=0.05, alpha=0.3)
    frame = s.material('window_frame', '#f2f2ee', roughness=0.5)
    shade = s.material('lamp_shade', '#f3ead8', roughness=0.9, emissive='#6b5a3a')

    # пол и стены: задняя, левая; в правой — окно
    s.box(floor, (0, -0.025, 0), (W, 0.05, D))
    s.box(wall, (0, H / 2, -half_d - T / 2), (W + 2 * T, H, T))
    s.box(wall, (-half_w - T / 2, H / 2, 0), (T, H, D))

    win_w, win_h, sill = 1.8, 1.5, 0.8
    win_z = -0.1
    x = half_w + T / 2
    s.box(wall, (x, sill / 2, 0), (T, sill, D))                                   # под окном
    s.box(wall, (x, (sill + win_h + H) / 2, 0), (T, H - sill - win_h, D))        # над окном
    seg_back = (win_z - win_w / 2) - (-half_d)
    s.box(wall, (x, sill + win_h / 2, -half_d + seg_back / 2), (T, win_h, seg_back))
    seg_front = half_d - (win_z + win_w / 2)
    s.box(wall, (x, sill + win_h / 2, half_d - seg_front / 2), (T, win_h, seg_front))
    s.box(glass, (x, sill + win_h / 2, win_z), (0.02, win_h, win_w))
    s.box(frame, (x - 0.06, sill - 0.02, win_z), (0.2, 0.04, win_w + 0.1))        # подоконник
    s.box(frame, (x, sill + win_h / 2, win_z), (0.06, win_h, 0.04))              # импост
    for dz in (-1, 1):                                                           # шторы
        s.box(curtain, (half_w - 0.08, (H - 0.1) / 2, win_z + dz * (win_w / 2 + 0.2)), (0.06, H - 0.1, 0.45))
    s.box(metal, (half_w - 0.12, H - 0.12, win_z), (0.03, 0.03, win_w + 1.0))      # карниз

    # плинтусы
    s.box(base, (0, 0.04, -half_d + 0.01), (W, 0.08, 0.02))
    s.box(base, (-half_w + 0.01, 0.04, 0), (0.02, 0.08, D))

    # кровать у задней стены
    twin = capacity >= 3
    bed_w = 1.6 if not twin else 2.0
    bed_l = 2.0
    bed_z = -half_d + bed_l / 2 + 0.05
    s.box(head, (0, 0.65, -half_d + 0.05), (bed_w + 0.6, 1.3, 0.1))                # мягкое изголовье
    s.box(wood, (0, 0.17, bed_z), (bed_w, 0.3, bed_l))                            # каркас
    s.box(linen, (0, 0.43, bed_z), (bed_w - 0.04, 0.22, bed_l - 0.04))            # матрас
    s.box(blanket, (0, 0.56, bed_z + 0.25), (bed_w + 0.02, 0.05, bed_l - 0.5))     # покрывало
    s.box(runner, (0, 0.59, bed_z + 0.65), (bed_w + 0.04, 0.03, 0.4))              # дорожка в ногах
    pillow_n = 2 if not twin else 3
    for i in range(pillow_n):
        px = -bed_w / 2 + bed_w * (i + 0.5) / pillow_n
        s.box(linen, (px, 0.63, -half_d + 0.35), (bed_w / pillow_n - 0.1, 0.16, 0.4))

    # тумбочки и лампы
    for side in (-1, 1):
        nx = side * (bed_w / 2 + 0.38)
        s.box(wood, (nx, 0.25, -half_d + 0.3), (0.5, 0.5, 0.45))
        s.box(metal, (nx, 0.32, -half_d + 0.53), (0.18, 0.02, 0.01))               # ручка ящика
        s.cylinder(metal, (nx, 0.5, -half_d + 0.3), 0.07, 0.07, 0.02)
        s.cylinder(metal, (nx, 0.52, -half_d + 0.3), 0.012, 0.012, 0.3)
        s.cylinder(shade, (nx, 0.78, -half_d + 0.3), 0.15, 0.11, 0.22)

    # ковёр в ногах
    s.box(rug, (0, 0.006, bed_z + bed_l / 2 + 0.2), (bed_w + 0.8, 0.012, 1.4))

    # левая стена: тумба с телевизором и шкаф у входа
    s.box(wood, (-half_w + 0.25, 0.3, 0.6), (0.45, 0.45, 1.6))
    s.box(wood, (-half_w + 0.25, 0.04, 0.6), (0.4, 0.08, 1.5))
    s.box(screen, (-half_w + 0.04, 1.3, 0.6), (0.04, 0.62, 1.1))
    s.box(metal, (-half_w + 0.02, 1.3, 0.6), (0.02, 0.66, 1.14))
    s.box(wood, (-half_w + 0.31, 1.1, 1.95), (0.6, 2.2, 1.0))                     # шкаф
    for dz in (-0.04, 0.04):
        s.box(metal, (-half_w + 0.62, 1.1, 1.95 + dz), (0.02, 0.3, 0.02))           # ручки
    s.box(base, (-half_w + 0.615, 1.1, 1.95), (0.005, 2.18, 0.01))               # шов дверей

    # правая стена: стол и стул ближе к входу
    desk_z = 1.85
    s.box(wood, (half_w - 0.3, 0.74, desk_z), (0.55, 0.04, 1.1))                  # столешница
    for dz in (-0.5, 0.5):
        s.box(wood, (half_w - 0.3, 0.37, desk_z + dz), (0.5, 0.72, 0.04))
    s.cylinder(shade, (half_w - 0.35, 0.76, desk_z - 0.35), 0.08, 0.06, 0.18)       # настольная лампа
    cx = half_w - 0.85
    s.box(chair, (cx, 0.46, desk_z), (0.46, 0.06, 0.46))                         # сиденье
    s.box(chair, (cx - 0.21, 0.75, desk_z), (0.04, 0.55, 0.44))                  # спинка
    for lx in (-0.19, 0.19):
        for lz in (-0.19, 0.19):
            s.box(metal, (cx + lx, 0.22, desk_z + lz), (0.03, 0.44, 0.03))

    # картина над столом
    s.box(frame, (half_w - 0.02, 1.65, desk_z + 0.05), (0.03, 0.55, 0.75))
    s.box(runner, (half_w - 0.035, 1.65, desk_z + 0.05), (0.01, 0.47, 0.67))

    return s.to_glb(name=name)
