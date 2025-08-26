import discord
from discord.ext import commands
import re
from db import link_ign  # Import the link_ign function from db.py


class RegisterCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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

    @commands.hybrid_command(
        name="register",
        description="Register a user with an IGN. Targets: me, @user, or user ID."
    )
    async def register(self, ctx: commands.Context, target: str, ign: str):
        print(
            f"Received register command from {ctx.author} with target: {target}, ign: {ign}")
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

            # Use the link_ign function from db.py to handle the database operation
            try:
                # Call the function with IGN and Discord ID
                link_ign(ign, str(user.id))
                await ctx.send(f"Registered user {user.display_name} (ID: {user.id}) as `{ign}`.")
            except Exception as e:
                print(f"Error in register command: {e}")
                await ctx.send(f"An error occurred while registering: {e}")

        except Exception as e:
            print(f"Error in register command: {e}")
            await ctx.send(f"An error occurred: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(RegisterCog(bot))
