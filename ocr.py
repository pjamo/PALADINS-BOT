# ocr_fixed.py — uses debug's manual row starts & shifts
import os
import json
import cv2
import numpy as np
from PIL import Image
import imagehash
import pytesseract
import re
import sys
from typing import Dict

# -------------------------------
# Paths / IO
# -------------------------------
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

IMG_PATH = sys.argv[1]
HASH_JSON = "champion_hashes.json"
OUTPUT_JSON = "parsed_scoreboard2.json"

# -------------------------------
# Geometry (from debug.py)
# -------------------------------
ICON_W, ICON_H = 228, 101

# Column boxes RELATIVE to the row's top (y_start)
PLAYER_BOXES = {
    "player":   (140, 0, 460, 62),   # height 62 per debug
    "credits":  (620, 0, 790, 100),
    "KDA":      (795, 0, 1010, 100),
    "damage":   (1020, 0, 1260, 100),
    "taken":    (1270, 0, 1500, 100),
    "objective_time": (1510, 0, 1650, 100),
    "shielding":      (1660, 0, 1910, 100),
    "healing":        (1920, 0, 2140, 100),
}

# Debug-aligned per-row Y starts (edit only these if a row needs nudging)
TEAM1_STARTS = [60, 180, 302, 422, 544]
TEAM2_STARTS = [927, 1042, 1160, 1274, 1392]

# Global nudge
X_SHIFT = 122
Y_SHIFT = 7

# Match-level boxes (from debug)
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
# Helpers
# -------------------------------


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
        # Fallback: build tops from manual row starts; icons sit a few px above text rows
        row_starts = TEAM1_STARTS + TEAM2_STARTS
        guess_tops = [max(0, y - 4) for y in row_starts]
        champs = [(4, y, ICON_W, ICON_H) for y in guess_tops][:10]
    else:
        # convert (x,y,w,h) -> (x,y,w,h) as expected; caller will slice with y:y+h etc.
        pass

    return champs[:10]


def extract_region(img, box):
    x1, y1, x2, y2 = box
    return img[y1:y2, x1:x2]


def load_player_whitelist(file_path: str) -> list:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Whitelist file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "players" not in data or not isinstance(data["players"], list):
        raise ValueError(f"Invalid whitelist format in {file_path}")
    return data["players"]


def load_map_whitelist(file_path: str) -> list:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Map whitelist file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "maps" not in data or not isinstance(data["maps"], list):
        raise ValueError(f"Invalid map whitelist format in {file_path}")
    return data["maps"]


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


def match_map_name(ocr_result: str, map_whitelist: list) -> str:
    closest_match, min_distance = None, float("inf")
    for map_name in map_whitelist:
        d = levenshtein_distance(ocr_result, map_name)
        if d < min_distance:
            closest_match, min_distance = map_name, d
    return closest_match if closest_match else ocr_result


def to_int(val: str) -> int:
    val = val.replace(",", "").strip()
    return int(val) if val.isdigit() else 0


def parse_kda(kda_str: str):
    m = re.match(r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)", kda_str.replace(" ", ""))
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return 0, 0, 0


def parse_match_data(img):
    match_data = {}
    map_whitelist_file = "maps.json"
    map_whitelist = load_map_whitelist(map_whitelist_file)

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
            match_data[key] = match_map_name(text, map_whitelist)
        else:
            match_data[key] = text

    return match_data

# -------------------------------
# Main
# -------------------------------


def main():
    img = cv2.imread(IMG_PATH)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {IMG_PATH}")

    hashes = load_hashes(HASH_JSON)

    # Match ID from filename
    match_id = int(''.join(filter(str.isdigit, os.path.basename(IMG_PATH))))

    # Load whitelists
    whitelist_file = "players.json"
    whitelist = load_player_whitelist(whitelist_file)

    # Detect champions (10 rows)
    champ_boxes = detect_champion_boxes(img)
    champs = [match_champion(img[y:y+h, x:x+w], hashes)
              for (x, y, w, h) in champ_boxes]

    # Build flat row list and process
    team1, team2 = [], []
    row_starts = TEAM1_STARTS + TEAM2_STARTS
    unmatched_players = []

    for i, y_start in enumerate(row_starts):
        team = team1 if i < len(TEAM1_STARTS) else team2
        pdata = {"champion": champs[i] if i < len(champs) else "Unknown"}

        for key, (x1, y1, x2, y2) in PLAYER_BOXES.items():
            box = (x1 + X_SHIFT,
                   y_start + y1 + Y_SHIFT,
                   x2 + X_SHIFT,
                   y_start + y2 + Y_SHIFT)

            if key == "player":
                val = ocr_text(img, box, whitelist, unmatched_players)
                pdata["player"] = val
            elif key == "credits":
                val = pytesseract.image_to_string(
                    extract_region(img, box), config="--psm 7").strip()
                pdata["credits"] = to_int(val)
            elif key == "KDA":
                val = pytesseract.image_to_string(
                    extract_region(img, box), config="--psm 7").strip()
                k, d, a = parse_kda(val)
                pdata["kills"], pdata["deaths"], pdata["assists"] = k, d, a
            else:
                val = pytesseract.image_to_string(
                    extract_region(img, box), config="--psm 7").strip()
                pdata[key] = to_int(val)

        team.append(pdata)

    # Try to match any leftover player OCRs to whitelist
    matched_players = set(p['player'] for p in team1 + team2)
    unmatched_ocr = [p['player'] for p in team1 + team2 if p['player']
                     not in matched_players or p['player'] in unmatched_players]
    # Remove already matched whitelist names
    unmatched_whitelist = [
        name for name in whitelist if name not in matched_players]
    # Assign closest whitelist name to each unmatched OCR result
    while unmatched_whitelist and unmatched_ocr:
        best_pair = None
        best_dist = float('inf')
        for ocr_name in unmatched_ocr:
            for whitelist_name in unmatched_whitelist:
                dist = levenshtein_distance(ocr_name, whitelist_name)
                if dist < best_dist:
                    best_dist = dist
                    best_pair = (ocr_name, whitelist_name)
        if best_pair:
            ocr_name, whitelist_name = best_pair
            # Update the player entry with the whitelist value
            for team in (team1, team2):
                for pdata in team:
                    if pdata['player'] == ocr_name:
                        pdata['player'] = whitelist_name
                        matched_players.add(whitelist_name)
                        break
            unmatched_ocr.remove(ocr_name)
            unmatched_whitelist.remove(whitelist_name)
    # Add any remaining whitelist players not matched in OCR
    for name in whitelist:
        if name not in matched_players:
            # Add to team1 if less than 5, else team2
            target_team = team1 if len(team1) < len(TEAM1_STARTS) else team2
            target_team.append({'player': name, 'champion': 'Unknown'})

    # Match-level info
    match_data = parse_match_data(img)
    match_data["match_id"] = match_id

    out = {"match": match_data, "teams": {"team1": team1, "team2": team2}}
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ Wrote {OUTPUT_JSON}")

# Optional utility: add match_id into an existing JSON


def add_match_id_to_json(file_path):
    try:
        file_name = os.path.basename(file_path)
        match_id = int(''.join(filter(str.isdigit, file_name)))
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        data['match']['match_id'] = match_id
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        print(f"Added match_id {match_id} to {file_path}")
    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except json.JSONDecodeError:
        print(f"Invalid JSON format in file: {file_path}")
    except ValueError:
        print(
            f"Could not generate a valid match_id from the file name: {file_name}")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
