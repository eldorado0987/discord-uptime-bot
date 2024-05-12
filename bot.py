import discord
from discord.ext import commands, tasks
import requests
import re
from requests.exceptions import ConnectionError
from PIL import Image, ImageDraw


# Your bot token
TOKEN = ''

# Initialize the bot with the specified intents
bot = commands.Bot(command_prefix='/', intents=discord.Intents.all())

#colors = {'grey': '[1;30m| ', 'red': '[1;31m| ', 'green': '[1;36m| ', 'orange': '[1;33m| '}
colors = {'grey': '#888987', 'red': '#e73746', 'green': '#59e98f', 'orange': '#ffd800'}

# Function to check the server status
def check_server(url):
    try:
        response = requests.get(url)
        # Check specific status codes
        if response.status_code == 200 or 403:
            return '**Server is up!**', discord.Color.green()
        else:
            return f'**Server returned status code {response.status_code}**', discord.Color.orange()
    except ConnectionError as e:
        if "WinError 10061" in str(e):
            return '**Server is up!**', discord.Color.green()
        else:
            print("에러 메시지:", e)
            return f'**Server is down!**\nError: {e}', discord.Color.red()

# Dictionary to keep track of tasks
monitor_tasks = {}
bar_tasks = {}

async def create_image(bar):
    # Define image size and bar dimensions
    image_width = 2000
    image_height = 250
    bar_width = image_width // (len(bar) * 2 + 1) + 0.85 # Adjusted for spaces
    bar_height = 200
    corner_radius = 30  # Increased corner radius for more roundness

    # Create a new image with white background
    image = Image.new('RGB', (image_width, image_height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    # Draw each bar segment with the corresponding color and space
    for i, color in enumerate(bar):
        x1 = (i * 2 + 1) * bar_width  # Adjusted for spaces
        y1 = 25
        x2 = (i * 2 + 2) * bar_width  # Adjusted for spaces
        y2 = y1 + bar_height
        draw.rounded_rectangle([(x1, y1), (x2, y2)], corner_radius, fill=color)

    return image

def create_task(loop_time, function, *args):
    @tasks.loop(seconds=loop_time)
    async def task():
        await function(*args)
    return task
def get_bar_color(color):
    if color == discord.Color.green():
        return 'green'
    elif color == discord.Color.orange():
        return 'orange'
    elif color == discord.Color.red():
        return 'red'

async def update_status(channel_id, url):  # Add channel_id as a parameter
    global bar_tasks
    status_message, color = check_server(url)
    bar = bar_tasks[channel_id]
    bar.pop(0)
    bar.append(colors[get_bar_color(color)])
    bar_tasks[channel_id] = bar
    image = await create_image(bar)
    image.save('status_image.png')  # Save the image as a file
    file = discord.File('status_image.png', filename='image.png')
    embed = discord.Embed(title="Server Status", description=f'{status_message}', color=color)
    embed.set_image(url='attachment://image.png')  # Set the image as an attachment in the embed
    message, _ = monitor_tasks[channel_id]  # Remove the 'task' variable
    await message.edit(embed=embed, attachments=[file])  # Await the message.edit() method call

# Slash command to start monitoring
@bot.tree.command(name='ping', description='Monitor a server and check its status every 5 minutes')
async def ping(interaction: discord.Interaction, url: str):
    global monitor_tasks, bar_tasks
    
    # Check if there is already a running task for this channel
    if interaction.channel_id in monitor_tasks:
        await interaction.response.send_message("Already monitoring in this channel. Please stop the previous monitor first.", ephemeral=True)
        return
    
    
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'https://' + url
    url_pattern = re.compile(r'^.*$')
    if not url_pattern.match(url):
        await interaction.response.send_message("This is not a valid URL format.", ephemeral=True)
        return

    # Send an initial message
    bar = [colors['grey']] * 20
    bar_tasks[interaction.channel_id] = bar
    await interaction.response.defer()
    message = await interaction.original_response()

    task = create_task(300, update_status, interaction.channel_id, url)
    monitor_tasks[interaction.channel_id] = message, task
    task.start()

# Function to stop monitoring
@bot.tree.command(name='stop', description='Stop monitoring the server status in this channel')
async def stop(interaction: discord.Interaction):
    global monitor_tasks

    # Stop the task if it exists and delete the message
    if interaction.channel_id in monitor_tasks:
        message, task = monitor_tasks[interaction.channel_id]
        task.cancel()
        try:
            await message.delete()
        except discord.NotFound:
            await interaction.response.send_message("The monitoring message was already deleted.", ephemeral=True)
        else:
            await interaction.response.send_message("Stopped monitoring and deleted the status message.", ephemeral=True)
        del monitor_tasks[interaction.channel_id]
    else:
        await interaction.response.send_message("No active monitoring in this channel.", ephemeral=True)

        

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.tree.sync()

bot.run(TOKEN)
