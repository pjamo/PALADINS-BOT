# debug_boxes_by_row_start.py
import cv2

# -------------------------------
# Config
# -------------------------------
IMG_PATH = "1273609932.png"
OUT_PATH = "debug_all_boxes.png"

# Column boxes are RELATIVE to a row's top (y_start). Do not change
ADJUSTED_BOXES = {
    "player":   (140, 0,    460, 62),
    "credits":  (620, 0,    790, 100),
    "KDA":      (795, 0,    1010, 100),
    "damage":   (1020, 0,   1260, 100),
    "taken":    (1270, 0,   1500, 100),
    "objective_time": (1510, 0, 1650, 100),
    "shielding":      (1660, 0, 1910, 100),
    "healing":        (1920, 0, 2140, 100),
}

# You only change these: the absolute starting Y of each row
# (Pre-filled with your current auto-calculated values as a starting point)
TEAM1_STARTS = [60, 180, 302, 422, 544]
TEAM2_STARTS = [927, 1042, 1160, 1274, 1392]

# Global shifts if the entire table needs nudging left/right/up/down
X_SHIFT = 122
Y_SHIFT = 7

# Match-level boxes (unchanged; independent of rows)
MATCH_BOXES = {
    "duration":     (150, 720, 400, 770),
    "region":       (150, 770, 480, 820),
    "map":          (150, 820, 650, 880),
    "team1_score":  (1050, 670, 1090, 730),
    "team2_score":  (1050, 830, 1090, 880),
}
MATCH_X_SHIFT = 370
MATCH_Y_SHIFT = 32

# -------------------------------
# Drawing
# -------------------------------


def draw_boxes():
    img = cv2.imread(IMG_PATH)

    colors = {
        "player": (0, 255, 0),
        "credits": (255, 0, 0),
        "KDA": (0, 0, 255),
        "damage": (255, 255, 0),
        "taken": (255, 0, 255),
        "objective_time": (0, 255, 255),
        "shielding": (128, 0, 255),
        "healing": (0, 128, 255),
        "duration": (255, 128, 0),
        "region":   (128, 255, 0),
        "map":      (0, 128, 255),
        "team1_score": (255, 0, 128),
        "team2_score": (0, 255, 128),
    }

    def draw_row(y_start):
        for key, (x1, y1, x2, y2) in ADJUSTED_BOXES.items():
            box = (
                x1 + X_SHIFT,
                y_start + y1 + Y_SHIFT,
                x2 + X_SHIFT,
                y_start + y2 + Y_SHIFT,
            )
            cv2.rectangle(img, (box[0], box[1]), (box[2], box[3]), colors.get(
                key, (255, 255, 255)), 2)
            cv2.putText(img, key, (box[0], box[1] - 5), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, colors.get(key, (255, 255, 255)), 1)

    # --- Team 1 rows (edit TEAM1_STARTS to adjust vertically)
    for y in TEAM1_STARTS:
        draw_row(y)

    # --- Team 2 rows (edit TEAM2_STARTS to adjust vertically)
    for y in TEAM2_STARTS:
        draw_row(y)

    # --- Match data (independent)
    for key, (x1, y1, x2, y2) in MATCH_BOXES.items():
        box = (x1 + MATCH_X_SHIFT, y1 + MATCH_Y_SHIFT,
               x2 + MATCH_X_SHIFT, y2 + MATCH_Y_SHIFT)
        cv2.rectangle(img, (box[0], box[1]), (box[2], box[3]),
                      colors.get(key, (200, 200, 200)), 2)
        cv2.putText(img, key, (box[0], box[1] - 5), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, colors.get(key, (200, 200, 200)), 1)

    cv2.imwrite(OUT_PATH, img)
    print(f"Debug image written to {OUT_PATH}")


if __name__ == "__main__":
    draw_boxes()
