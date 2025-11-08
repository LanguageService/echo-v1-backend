from enum import Enum


class Platform(Enum):
    SMS = "SMSM"
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"

    @classmethod
    def choices(cls):
        return [(member.value, member.name) for member in cls]
