import sqlite3


def update_discord_id(old_discord_id, new_discord_id):
    """
    Updates the Discord ID for an existing player by looking up the player via old_discord_id and linking the new Discord ID to it.
    """
    conn = sqlite3.connect("match_data.db")
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT player_id FROM players WHERE discord_id = ?;", (old_discord_id,))
        result = cursor.fetchone()
        if result:
            player_id = result[0]
            cursor.execute(
                "UPDATE players SET discord_id = ? WHERE player_id = ?;", (new_discord_id, player_id))
            conn.commit()
            print(
                f"Updated Discord ID for player_id {player_id} from {old_discord_id} to {new_discord_id}.")
        else:
            print(f"No player found with Discord ID {old_discord_id}.")
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()


def create_database():
    conn = sqlite3.connect("match_data.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        match_id INTEGER PRIMARY KEY, -- Unique match ID,
        queue_num INTEGER,
        time_minutes INTEGER,
        region TEXT,
        map TEXT,
        team1_score INTEGER,
        team2_score INTEGER,
        won INTEGER CHECK(won IN (0, 1)) -- 1 if team1 won, 0 otherwise
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS players (
        player_id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_ign TEXT UNIQUE,
        discord_id TEXT UNIQUE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS player_stats (
        player_stats_id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER,
        player_id INTEGER,
        team TEXT CHECK(team IN ('team1', 'team2')),
        champion TEXT,
        credits INTEGER,
        kills INTEGER,
        deaths INTEGER,
        assists INTEGER,
        damage INTEGER,
        taken INTEGER,
        objective_time INTEGER,
        shielding INTEGER,
        healing INTEGER,
        FOREIGN KEY (match_id) REFERENCES matches(match_id),
        FOREIGN KEY (player_id) REFERENCES players(player_id)
    );
    """)

    conn.commit()
    conn.close()


def insert_scoreboard(scoreboard, queue_num):
    conn = sqlite3.connect("match_data.db")
    cursor = conn.cursor()

    try:
        match = scoreboard["match"]
        match_id = match.get("match_id")
        team1_score = match["team1_score"]
        team2_score = match["team2_score"]
        won = 1 if team1_score > team2_score else 0

        cursor.execute("""
        SELECT 1 FROM matches WHERE match_id = ?;
        """, (match_id,))
        if cursor.fetchone():
            print(
                f"Warning: Match with match_id {match_id} already exists. Skipping insertion.")
            return

        cursor.execute("""
        INSERT INTO matches (match_id, queue_num, time_minutes, region, map, team1_score, team2_score, won)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (match_id, queue_num, match["time_minutes"], match["region"], match["map"], team1_score, team2_score, won))

        for player in scoreboard["teams"]["team1"]:
            cursor.execute("""
            SELECT player_id FROM players WHERE player_ign = ?;
            """, (player["player"],))
            result = cursor.fetchone()

            if result:
                player_id = result[0]
                cursor.execute("""
                INSERT INTO player_stats (match_id, player_id, team, champion, credits, kills, deaths, assists, damage, taken, objective_time, shielding, healing)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (match_id, player_id, "team1", player["champion"], player["credits"], player["kills"], player["deaths"],
                      player["assists"], player["damage"], player["taken"], player["objective_time"], player["shielding"], player["healing"]))
            else:
                print(f"Error: Player '{player['player']}' is not registered.")

        for player in scoreboard["teams"]["team2"]:
            cursor.execute("""
            SELECT player_id FROM players WHERE player_ign = ?;
            """, (player["player"],))
            result = cursor.fetchone()

            if result:
                player_id = result[0]
                cursor.execute("""
                INSERT INTO player_stats (match_id, player_id, team, champion, credits, kills, deaths, assists, damage, taken, objective_time, shielding, healing)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (match_id, player_id, "team2", player["champion"], player["credits"], player["kills"], player["deaths"],
                      player["assists"], player["damage"], player["taken"], player["objective_time"], player["shielding"], player["healing"]))
            else:
                print(f"Error: Player '{player['player']}' is not registered.")

        conn.commit()
        print(f"Scoreboard for match_id {match_id} inserted successfully.")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        conn.rollback()

    finally:
        conn.close()


def link_ign(player_ign, discord_id):
    """
    Links a discord_id to an ign, creating a new entry if the discord_id does not exist.
    """
    conn = sqlite3.connect("match_data.db")
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT player_id FROM players WHERE discord_id = ?;", (discord_id,))
        result = cursor.fetchone()
        if result:
            cursor.execute("""
                UPDATE players SET player_ign = ? WHERE discord_id = ?;
            """, (player_ign, discord_id))
            print(f"Updated IGN for Discord ID {discord_id} to {player_ign}.")
        else:
            cursor.execute("""
                INSERT INTO players (player_ign, discord_id) VALUES (?, ?);
            """, (player_ign, discord_id))
            print(
                f"Created new player entry: IGN={player_ign}, Discord ID={discord_id}.")
        conn.commit()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()


def get_games_played(discord_id):
    """
    Get the number of games a user has played based on their Discord ID.
    """
    conn = sqlite3.connect("match_data.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM player_stats
            INNER JOIN players ON player_stats.player_id = players.player_id
            WHERE players.discord_id = ?;
        """, (discord_id,))
        result = cursor.fetchone()
        return result[0] if result else 0
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        conn.close()


def execute_select_query(sql_query):
    """
    Execute a SELECT SQL query and return the results.
    """
    conn = sqlite3.connect("match_data.db")
    cursor = conn.cursor()
    try:
        cursor.execute(sql_query)
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        raise e
    finally:
        conn.close()
