import discord
from discord.ext import commands
import aiohttp
import os
import subprocess
import asyncio
import dotenv
import sqlite3
# Import the new functions
from db import insert_scoreboard, update_discord_id, get_games_played, execute_select_query

dotenv.load_dotenv()

# Enable necessary intents for message content and members
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Initialize the bot with multiple prefixes
bot = commands.Bot(command_prefix=['--', '>>'], intents=intents)

# Directory to save downloaded images
SAVE_DIR = os.path.dirname(os.path.abspath(__file__))
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        # Load the register cog
        await bot.load_extension('register')
        print("Loaded register cog")
        # Guild-specific syncing (replace YOUR_GUILD_ID)
        synced = await bot.tree.sync(guild=discord.Object(id=1363341336341909535))
        print(f"Synced {len(synced)} command(s) to guild")
    except Exception as e:
        print(f"Failed to sync commands or load cog: {e}")
    try:
        # Global syncing as fallback
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s) globally")
    except Exception as e:
        print(f"Failed to sync commands globally: {e}")


@bot.command(name="link_disc", help="Update a player's Discord ID. Only for Executives.")
async def link_disc(ctx, old_id: str, new_id: str):
    """
    Command to update a player's Discord ID in the database.
    Only users with the 'Executive' role can use this command.
    """
    # Check if the user has the "Executive" role
    if not any(role.name == "Executive" for role in getattr(ctx.author, "roles", [])):
        await ctx.send("You need the 'Executive' role to use this command!")
        return

    try:
        # Call the update_discord_id function from db.py
        update_discord_id(old_id, new_id)
        await ctx.send(f"Successfully updated Discord ID from `{old_id}` to `{new_id}`.")
    except Exception as e:
        print(f"Error in link_disc command: {e}")
        await ctx.send(f"An error occurred while updating the Discord ID: {e}")


@bot.command(name="stats", help="Get the number of games a user has played.")
async def stats(ctx, target: str = "me"):
    """
    Command to get the number of games a user has played.
    """
    try:
        # Determine the Discord ID
        if target.lower() == "me":
            discord_id = str(ctx.author.id)
        else:
            # Extract the ID from a mention or raw input
            discord_id = target.strip("<@!>")

        # Call the get_games_played function from db.py
        games_played = get_games_played(discord_id)
        if games_played is not None:
            await ctx.send(f"User <@{discord_id}> has played in {games_played} games.")
        else:
            await ctx.send(f"User <@{discord_id}> is not registered.")
    except Exception as e:
        print(f"Error in stats command: {e}")
        await ctx.send("An error occurred while fetching the stats.")


@bot.command(name="query", help="Execute a SELECT SQL query. Only for Executives.")
async def query(ctx, *, sql_query: str):
    """
    Command to execute a SELECT SQL query. Only for Executives.
    """
    # Check if the user has the "Executive" role
    if not any(role.name == "Executive" for role in getattr(ctx.author, "roles", [])):
        await ctx.send("You need the 'Executive' role to use this command!")
        return

    try:
        # Call the execute_select_query function from db.py
        results = execute_select_query(sql_query)
        if results:
            formatted_results = "\n".join([str(row) for row in results])
            await ctx.send(f"Query Results:\n```\n{formatted_results}\n```")
        else:
            await ctx.send("No results found.")
    except Exception as e:
        print(f"Error in query command: {e}")
        await ctx.send(f"An error occurred while executing the query: {e}")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith('>>match'):
        print(f"Received >>match command from {message.author}")
        try:
            # Parse queue_id and match_id from the command
            _, queue_id, match_id = message.content.split()

            # Fetch the list of Discord IDs from the "neat queue" (mocked here)
            discord_ids = await fetch_neat_queue(queue_id)

            # Look up IGNs for the Discord IDs
            player_igns, unregistered_ids = fetch_player_igns(discord_ids)
            if unregistered_ids:
                mentions = " ".join(
                    [f"<@{discord_id}>" for discord_id in unregistered_ids])
                await message.channel.send(f"Error: The following users are not registered: {mentions}")
                return

            # Wait for the PaladinsAssistant bot to respond with the match image
            def check(m):
                return m.author.name == "PaladinsAssistant" and m.author.discriminator == "2894" and m.attachments

            bot_response = await bot.wait_for('message', check=check, timeout=60.0)

            if bot_response.attachments:
                attachment = bot_response.attachments[0]
                image_path = os.path.join(SAVE_DIR, f"{match_id}.png")
                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        if resp.status == 200:
                            with open(image_path, 'wb') as f:
                                f.write(await resp.read())
                            print(f"Image downloaded: {image_path}")

                            try:
                                # Run the OCR script and pass the player IGNs via stdin
                                process = subprocess.Popen(
                                    ['python', 'ocr.py', image_path],
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True,
                                )
                                stdout, stderr = process.communicate(
                                    input="\n".join(player_igns))

                                if process.returncode == 0:
                                    # Assuming the OCR script outputs a Python dictionary
                                    ocr_output = eval(stdout)
                                    insert_scoreboard(ocr_output, queue_id)
                                    await message.channel.send(f"Processed match {match_id} and updated the scoreboard.")
                                else:
                                    print(f"OCR error: {stderr}")
                                    await message.channel.send("Error processing the image.")
                            except Exception as e:
                                print(f"Error running ocr.py: {e}")
                                await message.channel.send("Error processing the image.")
                        else:
                            await message.channel.send("Failed to download the image.")
            else:
                await message.channel.send("No image found in the bot's response.")
        except ValueError:
            await message.channel.send("Invalid command format! Use `>>match <queue_id> <match_id>`.")
        except asyncio.TimeoutError:
            await message.channel.send("Timed out waiting for PaladinsAssistant's response.")
        except Exception as e:
            print(f"Error in >>match: {e}")
            await message.channel.send("An error occurred while processing the command.")

    await bot.process_commands(message)


def fetch_player_igns(discord_ids):
    """
    Fetches player IGNs for the given list of Discord IDs from the database.
    Returns a tuple: (list of IGNs, list of unregistered Discord IDs).
    """
    conn = sqlite3.connect("match_data.db")
    cursor = conn.cursor()
    player_igns = []
    unregistered_ids = []

    try:
        for discord_id in discord_ids:
            cursor.execute(
                "SELECT player_ign FROM players WHERE discord_id = ?;", (discord_id,))
            result = cursor.fetchone()
            if result:
                player_igns.append(result[0])
            else:
                unregistered_ids.append(discord_id)
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

    return player_igns, unregistered_ids


async def fetch_neat_queue(queue_id):
    """
    Mock function to fetch the list of Discord IDs from the neat queue.
    Replace this with the actual API call or logic to fetch the queue data.
    """
    # Mocked list of Discord IDs for demonstration purposes
    return [
        "123456789012345678", "234567890123456789", "345678901234567890",
        "456789012345678901", "567890123456789012", "678901234567890123",
        "789012345678901234", "890123456789012345", "901234567890123456",
        "012345678901234567"
    ]


# Replace with your actual bot token
bot.run(os.getenv("BOT_TOKEN"))
