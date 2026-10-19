"""Thai national ID (13-digit) mod-11 Luhn checksum validator."""


def is_valid_thai_id(id_str: str) -> bool:
    """Validate a 13-digit Thai national ID (mod-11 checksum). Never raises."""
    try:
        if len(id_str) != 13:
            return False
        if not id_str.isdigit():
            return False
        weights = [13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2]
        total = sum(int(id_str[i]) * weights[i] for i in range(12))
        check = (11 - (total % 11)) % 10
        return check == int(id_str[12])
    except Exception:
        return False
