import logging
from datetime import timedelta
import regex as re

TIME_RE_STRING = r"\s?".join(
    [
        r"((?P<weeks>\d+?)\s?(weeks?|w))?",
        r"((?P<days>\d+?)\s?(days?|d))?",
        r"((?P<hours>\d+?)\s?(hours?|hrs|hr?))?",
        r"((?P<minutes>\d+?)\s?(minutes?|mins?|m(?!o)))?",  # prevent matching "months"
        r"((?P<seconds>\d+)\s?(seconds?|secs?|s?))?",
    ]
)

TIME_RE = re.compile(TIME_RE_STRING, re.I)


def parse_timedelta(
    argument, maximum=None, minimum=None, allowed_units=None,
):
    matches = TIME_RE.match(argument)
    allowed_units = allowed_units or ["weeks", "days", "hours", "minutes", "seconds"]
    if matches:
        params = {k: int(v) for k, v in matches.groupdict().items() if v is not None}
        for k in params.keys():
            if k not in allowed_units:
                return None
        if params:
            delta = timedelta(**params)
            if maximum and maximum < delta:
                return None
            if minimum and delta < minimum:
                return None
            return delta
    return None


def seconds_to_resp(seconds):
    time_data = {
        "week": int(seconds // 604800),
        "day": int((seconds % 604800) // 86400),
        "hour": int((seconds % 86400) // 3600),
        "minute": int((seconds % 3600) // 60),
        "second": int(seconds % 60),
    }
    response = []
    for item in time_data:
        if time_data[item] > 0:
            response.append(
                f"{time_data[item]} {item}{'s' if time_data[item] > 1 else ''}"
            )
    response_str = ", ".join(response[:-1])
    return response_str + f"{' and ' if response_str != '' else ''}{response[-1]}"
