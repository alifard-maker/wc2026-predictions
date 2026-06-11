"""Official FIFA World Cup 2026 knockout schedule (matches 73–104)."""

from knockout_bracket import STAGE_BY_MATCH_NUMBER

# ET kickoff times from FIFA match schedule.
KNOCKOUT_FIXTURES = [
    {"match_number": 73, "date": "2026-06-28", "time": "15:00", "venue": "Los Angeles Stadium"},
    {"match_number": 74, "date": "2026-06-29", "time": "16:30", "venue": "Boston Stadium"},
    {"match_number": 75, "date": "2026-06-29", "time": "21:00", "venue": "Estadio Monterrey"},
    {"match_number": 76, "date": "2026-06-29", "time": "13:00", "venue": "Houston Stadium"},
    {"match_number": 77, "date": "2026-06-30", "time": "17:00", "venue": "New York New Jersey Stadium"},
    {"match_number": 78, "date": "2026-06-30", "time": "13:00", "venue": "Dallas Stadium"},
    {"match_number": 79, "date": "2026-06-30", "time": "21:00", "venue": "Mexico City Stadium"},
    {"match_number": 80, "date": "2026-07-01", "time": "12:00", "venue": "Atlanta Stadium"},
    {"match_number": 81, "date": "2026-07-01", "time": "20:00", "venue": "San Francisco Bay Area Stadium"},
    {"match_number": 82, "date": "2026-07-01", "time": "16:00", "venue": "Seattle Stadium"},
    {"match_number": 83, "date": "2026-07-02", "time": "19:00", "venue": "Toronto Stadium"},
    {"match_number": 84, "date": "2026-07-02", "time": "15:00", "venue": "Los Angeles Stadium"},
    {"match_number": 85, "date": "2026-07-02", "time": "23:00", "venue": "BC Place Vancouver"},
    {"match_number": 86, "date": "2026-07-03", "time": "18:00", "venue": "Miami Stadium"},
    {"match_number": 87, "date": "2026-07-03", "time": "21:30", "venue": "Kansas City Stadium"},
    {"match_number": 88, "date": "2026-07-03", "time": "14:00", "venue": "Dallas Stadium"},
    {"match_number": 89, "date": "2026-07-04", "time": "17:00", "venue": "Philadelphia Stadium"},
    {"match_number": 90, "date": "2026-07-04", "time": "13:00", "venue": "Houston Stadium"},
    {"match_number": 91, "date": "2026-07-05", "time": "16:00", "venue": "New York New Jersey Stadium"},
    {"match_number": 92, "date": "2026-07-05", "time": "20:00", "venue": "Mexico City Stadium"},
    {"match_number": 93, "date": "2026-07-06", "time": "15:00", "venue": "Dallas Stadium"},
    {"match_number": 94, "date": "2026-07-06", "time": "20:00", "venue": "Seattle Stadium"},
    {"match_number": 95, "date": "2026-07-07", "time": "12:00", "venue": "Atlanta Stadium"},
    {"match_number": 96, "date": "2026-07-07", "time": "16:00", "venue": "BC Place Vancouver"},
    {"match_number": 97, "date": "2026-07-09", "time": "16:00", "venue": "Boston Stadium"},
    {"match_number": 98, "date": "2026-07-10", "time": "15:00", "venue": "Los Angeles Stadium"},
    {"match_number": 99, "date": "2026-07-11", "time": "17:00", "venue": "Miami Stadium"},
    {"match_number": 100, "date": "2026-07-11", "time": "21:00", "venue": "Kansas City Stadium"},
    {"match_number": 101, "date": "2026-07-14", "time": "15:00", "venue": "Dallas Stadium"},
    {"match_number": 102, "date": "2026-07-15", "time": "15:00", "venue": "Atlanta Stadium"},
    {"match_number": 103, "date": "2026-07-18", "time": "17:00", "venue": "Miami Stadium"},
    {"match_number": 104, "date": "2026-07-19", "time": "15:00", "venue": "New York New Jersey Stadium"},
]


def fixture_rows() -> list[dict]:
    rows = []
    for f in KNOCKOUT_FIXTURES:
        num = f["match_number"]
        rows.append(
            {
                "match_number": num,
                "stage": STAGE_BY_MATCH_NUMBER[num],
                "match_date": f["date"],
                "match_time": f["time"],
                "venue": f["venue"],
                "sort_order": num,
            }
        )
    return rows
