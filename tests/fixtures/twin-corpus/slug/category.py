def to_url_key(name):
    text = name.lower().strip()
    pieces = []
    previous_was_separator = False
    for character in text:
        if character.isascii() and character.isalnum():
            pieces.append(character)
            previous_was_separator = False
        elif not previous_was_separator:
            pieces.append("-")
            previous_was_separator = True
    return "".join(pieces).strip("-")
