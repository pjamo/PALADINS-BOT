import discord
from discord.ext import commands
import sqlite3
import re
from datetime import datetime


class RegisterCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.init_db()

    def init_db(self):
        """Initialize the SQLite database and players table."""
        try:
            with sqlite3.connect('players.db') as conn:
                c = conn.cursor()
                c.execute(
                    '''
                    CREATE TABLE IF NOT EXISTS players (
                        discord_id TEXT PRIMARY KEY,
                        ign TEXT,
                        registered_at TEXT
                    )
                    '''
                )
                conn.commit()
                print("Database initialized successfully in RegisterCog.")
        except Exception as e:
            print(f"Database error in RegisterCog: {e}")

    def extract_user_id(self, target: str):
        """Extract user ID from mention format, plain ID, or 'me'."""
        if target.lower() == 'me':
            return None  # Special case handled separately

        # Remove < > @ ! characters from mentions like <@123> or <@!123>
        user_id_str = re.sub(r'[<@!>]', '', target)
        try:
            return int(user_id_str)
        except ValueError:
            return None

    @commands.hybrid_command(name="ping", description="Test if the bot is online")
    async def ping(self, ctx: commands.Context):
        print(f"Received ping command from {ctx.author}")
        await ctx.send('Pong! Bot is online.')

    @commands.hybrid_command(name="sync", description="Sync commands to this server (admin only)")
    async def sync(self, ctx: commands.Context):
        print(f"Received sync command from {ctx.author}")
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.")
            return

        if not ctx.author.guild_permissions.administrator:
            await ctx.send("You need admin permissions to sync commands!")
            return

        try:
            synced = await self.bot.tree.sync(guild=discord.Object(id=ctx.guild.id))
            await ctx.send(f"Synced {len(synced)} command(s) to this server")
        except Exception as e:
            await ctx.send(f"Failed to sync commands: {e}")

    @commands.hybrid_command(
        name="register",
        description="Register a user with an IGN. Targets: me, @user, or user ID."
    )
    async def register(self, ctx: commands.Context, target: str, ign: str):
        print(f"Received register command from {ctx.author} with target: {target}, ign: {ign}")
        try:
            if target.lower() == 'me':
                user = ctx.author
            else:
                # Only 'Executive' can register someone else
                if not any(role.name == 'Executive' for role in getattr(ctx.author, "roles", [])):
                    await ctx.send("You need the 'Executive' role to register someone else!")
                    return

                user_id = self.extract_user_id(target)
                if user_id is None:
                    await ctx.send(
                        "Invalid user format! Use `/register me <ign>`, `/register @user <ign>`, or `/register <user_id> <ign>`."
                    )
                    return

                try:
                    user = await self.bot.fetch_user(user_id)
                except discord.errors.NotFound:
                    await ctx.send(f"User with ID {user_id} not found!")
                    return

            with sqlite3.connect('players.db') as conn:
                c = conn.cursor()
                c.execute("SELECT ign FROM players WHERE discord_id = ?", (str(user.id),))
                existing = c.fetchone()

                if existing:
                    await ctx.send(
                        f"User {user.display_name} (ID: {user.id}) is already registered as `{existing[0]}`. "
                        f"Use `/changeign` to update."
                    )
                else:
                    c.execute(
                        "INSERT INTO players (discord_id, ign, registered_at) VALUES (?, ?, ?)",
                        (str(user.id), ign, datetime.utcnow().isoformat())
                    )
                    conn.commit()
                    await ctx.send(f"Registered user {user.display_name} (ID: {user.id}) as `{ign}`.")
        except Exception as e:
            print(f"Error in register command: {e}")
            await ctx.send(f"An error occurred: {e}")

    @commands.hybrid_command(
        name="changeign",
        description="Change a user's IGN. Targets: me, @user, or user ID."
    )
    async def changeign(self, ctx: commands.Context, target: str, new_ign: str):
        print(f"Received changeign command from {ctx.author} with target: {target}, new_ign: {new_ign}")
        try:
            if target.lower() == 'me':
                user = ctx.author
            else:
                # Only 'Executive' can change someone else's IGN
                if not any(role.name == 'Executive' for role in getattr(ctx.author, "roles", [])):
                    await ctx.send("You need the 'Executive' role to change someone else's IGN!")
                    return

                user_id = self.extract_user_id(target)
                if user_id is None:
                    await ctx.send(
                        "Invalid user format! Use `/changeign me <new_ign>`, `/changeign @user <new_ign>`, "
                        "or `/changeign <user_id> <new_ign>`."
                    )
                    return

                try:
                    user = await self.bot.fetch_user(user_id)
                except discord.errors.NotFound:
                    await ctx.send(f"User with ID {user_id} not found!")
                    return

            with sqlite3.connect('players.db') as conn:
                c = conn.cursor()
                c.execute("SELECT ign FROM players WHERE discord_id = ?", (str(user.id),))
                existing = c.fetchone()

                if not existing:
                    await ctx.send(f"User {user.display_name} (ID: {user.id}) is not registered. Use `/register` first.")
                else:
                    c.execute(
                        "UPDATE players SET ign = ?, registered_at = ? WHERE discord_id = ?",
                        (new_ign, datetime.utcnow().isoformat(), str(user.id))
                    )
                    conn.commit()
                    await ctx.send(f"Updated user {user.display_name} (ID: {user.id})'s IGN to `{new_ign}`.")
        except Exception as e:
            print(f"Error in changeign command: {e}")
            await ctx.send(f"An error occurred: {e}")

    @commands.hybrid_command(
        name="show",
        description="Show IGN info. Use: me, @user, user ID, or 'playerlist'."
    )
    async def show(self, ctx: commands.Context, target: str):
        print(f"Received show command from {ctx.author} with target: {target}")
        try:
            if target.lower() == 'me':
                user = ctx.author
                with sqlite3.connect('players.db') as conn:
                    c = conn.cursor()
                    c.execute("SELECT ign FROM players WHERE discord_id = ?", (str(user.id),))
                    result = c.fetchone()
                if result:
                    await ctx.send(f"Your IGN is: `{result[0]}`")
                else:
                    await ctx.send("You are not registered. Use `/register` to register yourself.")

            elif target.lower() == 'playerlist':
                if not any(role.name == 'Executive' for role in getattr(ctx.author, "roles", [])):
                    await ctx.send("You need the 'Executive' role to view the playerlist!")
                    return

                with sqlite3.connect('players.db') as conn:
                    c = conn.cursor()
                    c.execute("SELECT discord_id, ign FROM players ORDER BY ign")
                    players = c.fetchall()

                if not players:
                    await ctx.send("No players are currently registered.")
                else:
                    player_list = []
                    for discord_id, ign in players:
                        try:
                            user = await self.bot.fetch_user(int(discord_id))
                            player_list.append(f"{ign} - {user.display_name}")
                        except Exception:
                            player_list.append(f"{ign} - Unknown User")

                    message = "**Player List:**\n" + "\n".join(player_list)
                    if len(message) > 2000:
                        chunks = [player_list[i:i + 30] for i in range(0, len(player_list), 30)]
                        for i, chunk in enumerate(chunks):
                            chunk_message = f"**Player List (Part {i + 1}):**\n" + "\n".join(chunk)
                            await ctx.send(chunk_message)
                    else:
                        await ctx.send(message)

            else:
                user_id = self.extract_user_id(target)
                if user_id is None:
                    await ctx.send(
                        "Invalid format! Use `/show me`, `/show @user`, `/show <user_id>`, or `/show playerlist`."
                    )
                    return

                try:
                    user = await self.bot.fetch_user(user_id)
                except discord.errors.NotFound:
                    await ctx.send(f"User with ID {user_id} not found!")
                    return

                with sqlite3.connect('players.db') as conn:
                    c = conn.cursor()
                    c.execute("SELECT ign FROM players WHERE discord_id = ?", (str(user.id),))
                    result = c.fetchone()

                if result:
                    await ctx.send(f"{user.display_name}'s IGN is: `{result[0]}`")
                else:
                    await ctx.send(f"{user.display_name} is not registered.")
        except Exception as e:
            print(f"Error in show command: {e}")
            await ctx.send(f"An error occurred: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(RegisterCog(bot))
