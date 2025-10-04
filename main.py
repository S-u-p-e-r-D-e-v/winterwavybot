import asyncio
import os
import subprocess
from typing import Optional

import discord
from discord.ext import commands

from utils import (
    add_to_queue,
    remove_from_queue,
    get_queues,
    get_live_stats,
)
from tiktok_listener import run_tiktok_listener


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_DISCORD_BOT_TOKEN_HERE")
COMMAND_PREFIX = os.getenv("DISCORD_PREFIX", "!")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "2800"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")


@bot.command(name="me")
async def cmd_me(ctx: commands.Context, username: Optional[str] = None, *, game: Optional[str] = None):
    if not username or not game:
        await ctx.send("Usage: !me <username> <game>")
        return
    add_to_queue(game, username)
    await ctx.send(f"Added {username} to {game} queue.")


@bot.command(name="queue")
async def cmd_queue(ctx: commands.Context, *, game: Optional[str] = None):
    if not game:
        await ctx.send("Usage: !queue <game>")
        return
    queues = get_queues()
    users = queues.get(game.strip().lower(), [])

    embed = discord.Embed(title=f"Queue for {game}", color=0x2b7cff)
    if users:
        embed.add_field(name="Users", value="\n".join(f"- {u}" for u in users), inline=False)
    else:
        embed.description = "No users in queue."
    await ctx.send(embed=embed)


@bot.command(name="leave")
async def cmd_leave(ctx: commands.Context, username: Optional[str] = None, *, game: Optional[str] = None):
    if not username or not game:
        await ctx.send("Usage: !leave <username> <game>")
        return
    ok = remove_from_queue(game, username)
    if ok:
        await ctx.send(f"Removed {username} from {game} queue.")
    else:
        await ctx.send(f"{username} not found in {game} queue.")


@bot.command(name="tiktok")
async def cmd_tiktok(ctx: commands.Context):
    stats = get_live_stats()
    embed = discord.Embed(title="TikTok Live Stats", color=0x00cc99)
    embed.add_field(name="Connected", value="Yes" if stats.get("connected") else "No", inline=True)
    embed.add_field(name="Viewers", value=str(stats.get("viewers", 0)), inline=True)
    embed.add_field(name="Likes", value=str(stats.get("likes", 0)), inline=True)

    last_comment = stats.get("last_comment")
    if last_comment:
        comment_value = f"{last_comment.get('user')}: {last_comment.get('comment')}"
        embed.add_field(name="Last Comment", value=comment_value[:1024], inline=False)

    last_gift = stats.get("last_gift")
    if last_gift:
        gift_value = f"{last_gift.get('user')} → {last_gift.get('gift')} x{last_gift.get('repeat_count')}"
        embed.add_field(name="Last Gift", value=gift_value[:1024], inline=False)

    await ctx.send(embed=embed)


async def start_dashboard_subprocess():
    env = os.environ.copy()
    cmd = ["python", os.path.join(os.path.dirname(__file__), "dashboard.py")]
    proc = await asyncio.create_subprocess_exec(*cmd, env=env)
    return proc


async def main():
    dashboard_proc: Optional[asyncio.subprocess.Process] = None
    tiktok_task: Optional[asyncio.Task] = None
    try:
        # Start dashboard
        dashboard_proc = await start_dashboard_subprocess()

        # Start TikTok listener
        stop_event = asyncio.Event()
        tiktok_task = asyncio.create_task(run_tiktok_listener(stop_event))

        # Start Discord bot (blocking call wrapped into task)
        bot_task = asyncio.create_task(bot.start(DISCORD_TOKEN))

        await bot_task
    except KeyboardInterrupt:
        pass
    finally:
        # Stop TikTok listener
        if tiktok_task and not tiktok_task.done():
            tiktok_task.cancel()
            try:
                await tiktok_task
            except Exception:
                pass
        # Kill dashboard subprocess
        if dashboard_proc:
            try:
                dashboard_proc.terminate()
            except ProcessLookupError:
                pass


if __name__ == "__main__":
    asyncio.run(main())
