"""Unchanged fixed-font inference and calendar parser; no model training."""
import json
import re
from datetime import datetime
from pathlib import Path
import numpy as np
from PIL import ImageOps
WEEKDAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
PATTERN = re.compile(r"^(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2}):(\d{2}) (am|pm) (MON|TUE|WED|THU|FRI|SAT|SUN)$")
ALLOWED = {i: "0123456789" for i in list(range(10)) + list(range(11, 19))}
ALLOWED.update({2: "/", 5: "/", 13: ":", 16: ":", 20: "ap", 21: "m",
                23: "MTWFS", 24: "OUHERA", 25: "NEDUIT"})

def parse_text(text, expected_date):
    """No digit, punctuation, clock-boundary, or timezone repairs are permitted."""
    match = PATTERN.fullmatch(text)
    if not match:
        return {"candidate": "", "filename_date_agrees": False, "weekday_agrees": False, "issues": ["timestamp_format_failure"]}
    month, day, year, hour, minute, second = map(int, match.groups()[:6])
    ampm, weekday = match[7], match[8]
    if not 1 <= hour <= 12:
        return {"candidate": "", "filename_date_agrees": False, "weekday_agrees": False, "issues": ["invalid_12_hour_clock"]}
    hour = hour % 12 + (12 if ampm == "pm" else 0)
    try:
        timestamp = datetime(year, month, day, hour, minute, second)
    except ValueError as error:
        return {"candidate": "", "filename_date_agrees": False, "weekday_agrees": False, "issues": ["invalid_calendar_or_clock:" + str(error)]}
    date_ok = timestamp.date().isoformat() == expected_date
    weekday_ok = WEEKDAYS[timestamp.weekday()] == weekday
    issues = ([] if date_ok else ["filename_date_mismatch"]) + ([] if weekday_ok else ["weekday_mismatch"])
    return {"candidate": timestamp.isoformat(), "filename_date_agrees": date_ok, "weekday_agrees": weekday_ok,
            "issues": issues, "clock_phase_seconds": (minute % 10) * 60 + second}

class Recognizer:

    def __init__(self, path):
            self.model = json.loads(Path(path).read_text())
            self.characters = sorted(self.model["templates"])
            self.weights = np.zeros((len(self.characters), 64*32), dtype=np.float32)
            for i, character in enumerate(self.characters):
                template = self.model["templates"][character]
                self.weights[i, template["white_indices"]] = .5 / len(template["white_indices"])
                self.weights[i, template["black_indices"]] = -.5 / len(template["black_indices"])
            self.allowed = {position: [self.characters.index(c) for c in sorted(choices)] for position, choices in ALLOWED.items()}

    def recognize(self, image):
            if list(image.size) != self.model["image_dimensions"]:
                raise ValueError(f"Unexpected image dimensions {image.size}; fixed crop is not rescaled")
            crop = ImageOps.grayscale(image.crop(self.model["crop_xyxy"]))
            values = np.asarray(crop, dtype=np.float32) / 255
            cells = values.reshape(64,26,32).transpose(1,0,2).reshape(26,64*32)
            scores = .5 + np.einsum("kp,ip->ik", self.weights, cells, optimize=False)
            raw, details = [], []
            for position in range(26):
                if position in self.model["space_positions"]:
                    raw.append(" ")
                    continue
                options = self.allowed[position]
                order = sorted(options, key=lambda i: (-float(scores[position,i]), self.characters[i]))
                best = order[0]
                score = float(scores[position,best])
                margin = score - float(scores[position,order[1]]) if len(order) > 1 else 1.0
                raw.append(self.characters[best])
                details.append({"position": position, "character": self.characters[best], "score": score, "margin": margin})
            return "".join(raw), details
