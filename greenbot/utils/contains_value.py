def contains_value(values, _dict):
    for value in values:
        if not _dict.get(value, None):
            return False
    return True