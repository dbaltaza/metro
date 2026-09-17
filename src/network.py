
from pydantic import BaseModel, Field
from src.error import MetroError, StationError
from src.passenger import Passenger


class Station(BaseModel):
    name: str
    waiting: list[Passenger] = Field(default_factory=list)
    x: int = Field(ge=0, le=1000)
    y: int = Field(ge=0, le=1000)


class Line(BaseModel):
    name: str
    color: tuple[int, int, int]
    stations: list[str]


class Map(BaseModel):
    stations: dict[str, Station] = Field(default_factory=dict)
    lines: list[Line] = Field(default_factory=list)

    def add_station(self, station: Station) -> None:
        self.stations[station.name] = station

    def add_line(self, line: Line) -> None:
        for name in line.stations:
            if name not in self.stations:
                raise StationError(
                    f"Line {line.name!r} references unknown station {name!r}"
                )
        self.lines.append(line)

    def line_named(self, line_name: str) -> Line:
        for line in self.lines:
            if line.name == line_name:
                return line
        raise MetroError(f"No line named {line_name!r}")

    def next_station(self, line_name: str, station_name: str) -> str | None:
        for line in self.lines:
            if line.name == line_name:
                try:
                    i = line.stations.index(station_name)
                except ValueError:
                    raise StationError(
                        f"Station {station_name!r} is not on line {line_name!r}"
                    ) from None
                if i + 1 < len(line.stations):
                    return line.stations[i + 1]
                return None
        raise MetroError(f"No line named {line_name!r}")

    def lines_at(self, station_name: str) -> list:
        lines_at = []
        for line in self.lines:
            if station_name in line.stations:
                lines_at.append(line)
        return lines_at


AZUL = (36, 116, 184)
AMARELA = (240, 178, 24)
VERDE = (0, 150, 92)
VERMELHA = (203, 51, 48)

# Logical coordinates on a 0..1000 grid, laid out octilinearly: every
# segment runs horizontally, vertically or at 45 degrees.
_STATIONS: dict[str, tuple[int, int]] = {
    # Linha Azul, northwest to southeast
    "Reboleira": (20, 220),
    "Amadora Este": (60, 260),
    "Alfornelos": (100, 300),
    "Pontinha": (140, 340),
    "Carnide": (180, 380),
    "Colégio Militar/Luz": (220, 420),
    "Alto dos Moinhos": (260, 460),
    "Laranjeiras": (300, 500),
    "Jardim Zoológico": (340, 540),
    "Praça de Espanha": (380, 580),
    "São Sebastião": (420, 620),
    "Parque": (460, 620),
    "Marquês de Pombal": (500, 620),
    "Avenida": (540, 660),
    "Restauradores": (580, 700),
    "Baixa-Chiado": (580, 780),
    "Terreiro do Paço": (640, 820),
    "Santa Apolónia": (700, 820),
    # Linha Amarela, a vertical spine
    "Odivelas": (500, 180),
    "Senhor Roubado": (500, 220),
    "Ameixoeira": (500, 260),
    "Lumiar": (500, 300),
    "Quinta das Conchas": (500, 340),
    "Campo Grande": (500, 380),
    "Cidade Universitária": (500, 420),
    "Entre Campos": (500, 460),
    "Campo Pequeno": (500, 500),
    "Saldanha": (500, 540),
    "Picoas": (500, 580),
    "Rato": (460, 660),
    # Linha Verde
    "Telheiras": (440, 320),
    "Alvalade": (540, 420),
    "Roma": (580, 460),
    "Areeiro": (620, 500),
    "Alameda": (660, 540),
    "Arroios": (660, 580),
    "Anjos": (660, 620),
    "Intendente": (660, 660),
    "Martim Moniz": (660, 700),
    "Rossio": (620, 740),
    "Cais do Sodré": (540, 820),
    # Linha Vermelha
    "Aeroporto": (900, 140),
    "Encarnação": (900, 180),
    "Moscavide": (900, 220),
    "Oriente": (900, 260),
    "Cabo Ruivo": (900, 300),
    "Olivais": (860, 340),
    "Chelas": (820, 380),
    "Bela Vista": (780, 420),
    "Olaias": (740, 460),
}

_ROUTES: list[tuple[str, tuple[int, int, int], list[str]]] = [
    ("Linha Azul", AZUL, [
        "Reboleira", "Amadora Este", "Alfornelos", "Pontinha", "Carnide",
        "Colégio Militar/Luz", "Alto dos Moinhos", "Laranjeiras",
        "Jardim Zoológico", "Praça de Espanha", "São Sebastião", "Parque",
        "Marquês de Pombal", "Avenida", "Restauradores", "Baixa-Chiado",
        "Terreiro do Paço", "Santa Apolónia",
    ]),
    ("Linha Amarela", AMARELA, [
        "Odivelas", "Senhor Roubado", "Ameixoeira", "Lumiar",
        "Quinta das Conchas", "Campo Grande", "Cidade Universitária",
        "Entre Campos", "Campo Pequeno", "Saldanha", "Picoas",
        "Marquês de Pombal", "Rato",
    ]),
    ("Linha Verde", VERDE, [
        "Telheiras", "Campo Grande", "Alvalade", "Roma", "Areeiro", "Alameda",
        "Arroios", "Anjos", "Intendente", "Martim Moniz", "Rossio",
        "Baixa-Chiado", "Cais do Sodré",
    ]),
    ("Linha Vermelha", VERMELHA, [
        "Aeroporto", "Encarnação", "Moscavide", "Oriente", "Cabo Ruivo",
        "Olivais", "Chelas", "Bela Vista", "Olaias", "Alameda", "Saldanha",
        "São Sebastião",
    ]),
]


def build_demo_map() -> Map:
    """The Lisbon metro network, drawn on a 0..1000 logical grid."""
    m = Map()
    for name, (x, y) in _STATIONS.items():
        m.add_station(Station(name=name, x=x, y=y))
    for name, color, stations in _ROUTES:
        m.add_line(Line(name=name, color=color, stations=stations))
    return m
