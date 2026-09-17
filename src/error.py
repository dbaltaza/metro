
class MetroError(Exception):
    "Base Error"

class StationError(MetroError):
    "No station found"