import random
import sys

def luhn_check(card_number: str) -> bool:
    """Check if a card number is valid using the Luhn algorithm."""
    digits = [int(char) for char in card_number if char.isdigit()]
    if len(digits) != 16:
        return False
    
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            doubled = digit * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += digit
            
    return checksum % 10 == 0

def generate_card_number() -> str:
    """Generate a structurally valid 16-digit card number using Luhn algorithm."""
    # Start with a common identifier (4 for Visa, 5 for Mastercard)
    prefix = str(random.choice([4, 5]))
    body = "".join([str(random.randint(0, 9)) for _ in range(14)])
    partial_card = prefix + body
    
    digits = [int(char) for char in partial_card]
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 0:
            doubled = digit * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += digit
            
    check_digit = (10 - (checksum % 10)) % 10
    return partial_card + str(check_digit)

def generate_6_digit_pin() -> str:
    """Generate a random 6-digit security PIN."""
    return f"{random.randint(0, 999999):06d}"

def main():
    print("=" * 40)
    print("      TERMUX CARD & PIN GENERATOR       ")
    print("=" * 40)
    
    # Generate data
    card_num = generate_card_number()
    pin = generate_6_digit_pin()
    is_valid = luhn_check(card_num)
    
    # Output results
    print(f"[+] Generated Card : {card_num}")
    print(f"[+] 6-Digit PIN    : {pin}")
    print(f"[+] Luhn Validated : {is_valid}")
    print("=" * 40)

if __name__ == "__main__":
    main()
