# ocr_fixed.py — uses debug's manual row starts & shifts
import os
import cv2
import numpy as np
from PIL import Image
import imagehash
import pytesseract
import re
import sys
from typing import Dict, List

# -------------------------------
# Paths / IO
# -------------------------------
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

IMG_PATH = sys.argv[1]  # Image path passed as the only argument

ICON_W, ICON_H = 228, 101

PLAYER_BOXES = {
    "player":   (140, 0, 460, 62),
    "credits":  (620, 0, 790, 100),
    "KDA":      (795, 0, 1010, 100),
    "damage":   (1020, 0, 1260, 100),
    "taken":    (1270, 0, 1500, 100),
    "objective_time": (1510, 0, 1650, 100),
    "shielding":      (1660, 0, 1910, 100),
    "healing":        (1920, 0, 2140, 100),
}

TEAM1_STARTS = [60, 180, 302, 422, 544]
TEAM2_STARTS = [927, 1042, 1160, 1274, 1392]

X_SHIFT = 122
Y_SHIFT = 7

MATCH_BOXES = {
    "duration":     (150, 720, 400, 770),
    "region":       (150, 770, 480, 820),
    "map":          (150, 820, 650, 880),
    "team1_score":  (1050, 670, 1090, 730),
    "team2_score":  (1050, 830, 1090, 880),
}
MATCH_X_SHIFT = 370
MATCH_Y_SHIFT = 32


def load_hashes(path: str) -> Dict[str, imagehash.ImageHash]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: imagehash.hex_to_hash(v) for k, v in data.items() if isinstance(v, str)}


def phash(img_bgr: np.ndarray) -> imagehash.ImageHash:
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    return imagehash.phash(pil)


def match_champion(icon_bgr: np.ndarray,
                   hash_book: Dict[str, imagehash.ImageHash],
                   max_dist: int = 20) -> str:
    h = phash(icon_bgr)
    best_k, best_d = None, 9999
    for k, hv in hash_book.items():
        d = h - hv
        if d < best_d:
            best_k, best_d = k, d
    return best_k if best_d <= max_dist else "Unknown"


def detect_champion_boxes(img_bgr: np.ndarray):
    """Try to detect champ portraits; if not enough found, fall back to row-based tops."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, thr = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    cnts, _ = cv2.findContours(thr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = [cv2.boundingRect(c) for c in cnts]
    champs = [b for b in boxes if 180 < b[2] <
              260 and 80 < b[3] < 120 and b[0] < 80]
    champs = sorted(champs, key=lambda b: b[1])

    if len(champs) < 10:
        row_starts = TEAM1_STARTS + TEAM2_STARTS
        guess_tops = [max(0, y - 4) for y in row_starts]
        champs = [(4, y, ICON_W, ICON_H) for y in guess_tops][:10]
    else:
        pass

    return champs[:10]


def extract_region(img, box):
    x1, y1, x2, y2 = box
    return img[y1:y2, x1:x2]


def levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def ocr_text(img, box, whitelist, unmatched_players):
    roi = extract_region(img, box)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    thr = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 11, 2)
    kernel = np.ones((2, 2), np.uint8)
    thr = cv2.dilate(thr, kernel, iterations=1)
    text = pytesseract.image_to_string(
        thr,
        config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789öéàáèíòóùúÄÖÜäöüÉ",
        lang="eng"
    ).strip()
    text = re.sub(r"[^\w\söéàáèíòóùúÄÖÜäöüÉ]", "", text)
    print(f"OCR raw before matching: '{text}'")

    closest_match, min_distance = None, float("inf")
    for name in whitelist:
        d = levenshtein_distance(text, name)
        if d < min_distance:
            closest_match, min_distance = name, d
    if closest_match and min_distance <= 3:
        whitelist.remove(closest_match)
        return closest_match
    else:
        unmatched_players.append(text)
        print(f"⚠ Error: '{text}' not found in whitelist. Using raw value.")
        return text


def parse_match_data(img, players: List[str]):
    """
    Parse match data from the image and include the provided player list.
    """
    match_data = {}
    for key, (x1, y1, x2, y2) in MATCH_BOXES.items():
        box = (x1 + MATCH_X_SHIFT, y1 + MATCH_Y_SHIFT,
               x2 + MATCH_X_SHIFT, y2 + MATCH_Y_SHIFT)
        text = pytesseract.image_to_string(
            extract_region(img, box), config="--psm 7").strip()

        if key == "duration":
            m = re.search(r"(\d+)", text)
            match_data["time_minutes"] = int(m.group(1)) if m else 0
        elif key in ("team1_score", "team2_score"):
            m = re.search(r"(\d+)$", text)
            match_data[key] = int(m.group(1)) if m else 0
        elif key == "map":
            match_data[key] = text
        else:
            match_data[key] = text

    match_data["players"] = players
    return match_data


def main():
    if len(sys.argv) < 2:
        print("Usage: python ocr.py <image_path>")
        sys.exit(1)

    img = cv2.imread(IMG_PATH)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {IMG_PATH}")

    # Players will be passed via stdin (from run.py)
    players = sys.stdin.read().strip().split("\n")

    # Parse match data
    match_data = parse_match_data(img, players)

    # Output match data
    print(match_data)


if __name__ == "__main__":
    main()
