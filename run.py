import discord
from discord.ext import commands
import aiohttp
import os
import subprocess
import asyncio

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

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.startswith('>>match'):
        print(f"Received >>match command from {message.author}")
        try:
            match_id = message.content.split()[1].strip()

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
                                result = subprocess.run(
                                    ['python', 'ocr.py', image_path, match_id],
                                    capture_output=True,
                                    text=True
                                )
                                print(f"ocr.py output: {result.stdout}")
                                if result.stderr:
                                    print(f"ocr.py error: {result.stderr}")
                                await message.channel.send(f"Processed image for match {match_id}")
                            except Exception as e:
                                print(f"Error running ocr.py: {e}")
                                await message.channel.send("Error processing the image.")
                        else:
                            await message.channel.send("Failed to download the image.")
            else:
                await message.channel.send("No image found in the bot's response.")
        except IndexError:
            await message.channel.send("Please provide a valid match ID after >>match")
        except asyncio.TimeoutError:
            await message.channel.send("Timed out waiting for PaladinsAssistant's response.")
        except Exception as e:
            print(f"Error in >>match: {e}")
            await message.channel.send("An error occurred while processing the command.")

    await bot.process_commands(message)

# Replace with your actual bot token
bot.run('MTQwODE5NDUxNDMyOTUzNDU0Ng.G4Otp1.SfPdMOVqqJk_1heAAQIBQ0UApp9ZKX46IxAiNU')