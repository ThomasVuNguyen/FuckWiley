import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
from extractor import run_extraction

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Define bot intents
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Queue to hold extraction requests
extraction_queue = asyncio.Queue()

class ExtractionJob:
    def __init__(self, user, book_url, email, password, pages):
        self.user = user
        self.book_url = book_url
        self.email = email
        self.password = password
        self.pages = pages

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    # Start the background worker task to process the queue
    bot.loop.create_task(process_queue())

@bot.command()
async def clone(ctx):
    """Start an extraction request by DMing the user for details."""
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("I've sent you a DM to get your book details!")
    
    try:
        # Ask for details in DM
        await ctx.author.send("Hello! Let's clone a book on VitalSource.")
        
        await ctx.author.send("1. What is the URL of the first page you want to extract? (e.g. https://bookshelf.vitalsource.com/#/books/...)")
        url_msg = await bot.wait_for('message', check=lambda m: m.author == ctx.author and isinstance(m.channel, discord.DMChannel), timeout=60.0)
        book_url = url_msg.content.strip()

        await ctx.author.send("2. What is your VitalSource login Email?")
        email_msg = await bot.wait_for('message', check=lambda m: m.author == ctx.author and isinstance(m.channel, discord.DMChannel), timeout=60.0)
        email = email_msg.content.strip()

        await ctx.author.send("3. What is your VitalSource login Password? (This will be temporarily used directly by the bot and never saved)")
        password_msg = await bot.wait_for('message', check=lambda m: m.author == ctx.author and isinstance(m.channel, discord.DMChannel), timeout=60.0)
        password = password_msg.content.strip()

        await ctx.author.send("4. How many pages do you want to extract? (Enter a number)")
        pages_msg = await bot.wait_for('message', check=lambda m: m.author == ctx.author and isinstance(m.channel, discord.DMChannel), timeout=60.0)
        
        try:
            pages = int(pages_msg.content.strip())
        except ValueError:
            await ctx.author.send("That doesn't look like a valid number. Please run `!clone` again to restart.")
            return

        # Create job and add to queue
        job = ExtractionJob(ctx.author, book_url, email, password, pages)
        await extraction_queue.put(job)
        
        await ctx.author.send(f"Perfect! Your request has been added to the queue (Position: {extraction_queue.qsize()}). I'll let you know when it's done and send you the Markdown file.")
        print(f"Added job for {ctx.author}: {pages} pages of {book_url}")

    except asyncio.TimeoutError:
        await ctx.author.send("You took too long to respond! Run `!clone` again to restart.")

async def process_queue():
    """Background task that takes jobs from the queue and processes them one by one."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        job = await extraction_queue.get()
        print(f"Starting extraction job for {job.user.name}")
        
        try:
            await job.user.send(f"Status update: I'm starting to clone your book now! This might take a few minutes...")
            
            async def status_callback(msg):
                print(f"[{job.user.name}] {msg}")
                # We can choose to send all updates to discord or just print them.
                # await job.user.send(f"Status: {msg}")
            
            # Run the extraction (this might take a while)
            markdown_file = await run_extraction(job, status_callback)
            
            await job.user.send(f"✅ Your book has been fully extracted!")
            # Send the file back to the user
            with open(markdown_file, "rb") as file:
                await job.user.send("Here is your pristine Markdown copy:", file=discord.File(file, "extracted_book.md"))
            
        except Exception as e:
            await job.user.send(f"❌ An error occurred during extraction: {e}")
            print(f"Error processing job for {job.user}: {e}")
        finally:
            extraction_queue.task_done()

if __name__ == '__main__':
    if not TOKEN:
        print("ERROR: DISCORD_TOKEN is not set in the environment or .env file.")
    else:
        bot.run(TOKEN)
