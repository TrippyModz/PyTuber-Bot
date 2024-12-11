from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton, QLabel
from qasync import QEventLoop  # Import QEventLoop for async support with PyQt5
from playwright.async_api import async_playwright
import sys
import discord
import asyncio
import re

# Queue to hold YouTube URLs for PyQt5 app
youtube_queue = asyncio.Queue()

class YouTubeOpener(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Video Opener")
        self.setGeometry(100, 100, 400, 200)
        layout = QVBoxLayout()
        self.label = QLabel("Enter the YouTube video URL:", self)
        layout.addWidget(self.label)
        self.url_input = QLineEdit(self)
        layout.addWidget(self.url_input)
        self.continue_button = QPushButton("Continue", self)
        self.continue_button.clicked.connect(self.manual_video_open)  # Connect to method
        layout.addWidget(self.continue_button)
        self.setLayout(layout)

        self.current_tab = None
        self.browser = None
        self.default_tab = None
        self.context = None  # Add a reference to the browser context

    async def manual_video_open(self):
        """Manually open a video URL entered in the input field."""
        video_url = self.url_input.text()
        if video_url:
            await youtube_queue.put(video_url)
            print(f"Manually added video: {video_url}", flush=True)

    async def process_queue(self):
      async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        self.default_tab = await browser.new_page()

        while True:
            # Wait for video data (URL, playback speed, fullscreen)
            video_data = await youtube_queue.get()
            video_url, playback_speed, fullscreen = video_data

            # Open the video
            video_tab = await browser.new_page()
            await video_tab.goto(video_url)

            # Set playback speed
            await video_tab.evaluate(f"""
                () => {{
                    const video = document.querySelector('video');
                    if (video) {{
                        video.playbackRate = {playback_speed};
                    }}
                }}
            """)

            # Toggle fullscreen if requested
            if fullscreen:
                await video_tab.evaluate("""
                    () => {
                        const fullscreenBtn = document.querySelector('.ytp-fullscreen-button');
                        if (fullscreenBtn) {
                            fullscreenBtn.click();
                        }
                    }
                """)

                # Automatically retrieve the video's duration
                duration = await video_tab.evaluate('''() => {
                    const video = document.querySelector('video');
                    if (video) {
                        return video.duration;  // Get the duration in seconds
                    }
                    return 0;  // Return 0 if no video element is found
                }''')

                if duration > 0:
                    print(f"Video duration: {duration} seconds")
                    await asyncio.sleep(duration)  # Wait for the video to finish
                else:
                    print("Failed to retrieve video duration or no video found.")

                # Close the video tab after playback
                await video_tab.close()

class MyClient(discord.Client):
    def __init__(self, intents, yt_opener):
        super().__init__(intents=intents)
        self.yt_opener = yt_opener  # Reference to the YouTubeOpener instance

    async def on_ready(self):
        print(f"Logged in as {self.user}!", flush=True)
        
        # Send a message to a specific channel to announce the bot is online
        channel_id = 1234567890  # Replace with your target channel ID
        channel = self.get_channel(channel_id)
        if channel:
            await channel.send("PyTuber is ready to start playing")

async def on_message(self, message):
    if message.author == self.user:
        return  # Ignore bot's own messages

    if message.content.startswith("!play"):
        # Extract URL and options from the message
        command_pattern = r"!play\s+(https?://\S+)\s*(.*)"
        match = re.match(command_pattern, message.content)
        if match:
            video_url = match.group(1)
            options = match.group(2).strip()

            # Parse playback options
            playback_speed = 1.0
            fullscreen = False

            if "--speed" in options:
                speed_match = re.search(r"--speed\s+(\d+(\.\d+)?)", options)
                if speed_match:
                    playback_speed = float(speed_match.group(1))
            if "--fullscreen" in options:
                fullscreen = True

            await youtube_queue.put((video_url, playback_speed, fullscreen))
            await message.channel.send(f"✅ Added your video to the queue with a speed {playback_speed}x{' in fullscreen' if fullscreen else ''}")
        else:
            await message.channel.send("❌ Invalid command format. Use `!play <url> [--speed <value>] [--fullscreen]`")

    elif message.content.startswith("!view"):
        # Change the view mode (fullscreen/theater/default)
        view_mode = message.content.split(" ", 1)[-1].lower()
        if view_mode in ["fullscreen", "theater", "default"]:
            await self.yt_opener.change_view_mode(view_mode)
            await message.channel.send(f"✅ Changed view mode to {view_mode}.")
        else:
            await message.channel.send("❌ Invalid view mode. Use `!view fullscreen`, `!view theater`, or `!view default`.")


        # Respond to mentions
        if self.user in message.mentions:
            await message.channel.send(
                "Sorry I cannot speak with humans"
            )
            return

        # Commands for playback control
        if message.content.startswith("!pause"):
            if await self.yt_opener.pause_video():
                await message.channel.send("⏸ Hurry up and pee.")
            else:
                await message.channel.send("❌ Unable to pause the video.")

        elif message.content.startswith("!play"):
            if await self.yt_opener.resume_video():
                await message.channel.send("▶ Playing now!.")
            else:
                await message.channel.send("❌ Unable to play video.")
        
        elif message.content.startswith("!skip"):
            if await self.yt_opener.skip_video():
                await message.channel.send("⏩ Skipped the video! Onto the next")
            else:
                 await message.channel.send("❌ No video is playing or I can't skip it right now.")

        elif message.content.startswith("?help"):
            await message.channel.send(f"Here are the commands and how to enter them to adjust the stream to your liking! !play <YouTube URL> [--speed <number>] [--fullscreen]
             Example: !play https://youtu.be/xyz123 --speed 1.5 --fullscreen
             --speed: Adjust playback speed (e.g., 1.0 for normal speed, 1.5 for faster playback).
             --fullscreen: Start the video in fullscreen mode.
             !view <mode>
             mode can be fullscreen, theater, or default.
             Example: !view theater
             [!]play [!]pause [!]skip all work as their names imply!" )

        elif "youtube.com/watch" in message.content or "youtu.be/" in message.content:
            video_url = message.content.strip()
            try:
                await youtube_queue.put(video_url)
                await message.channel.send(f"✅ Added to queue.")
            except Exception as e:
                await message.channel.send(f"❌ Failed to process the video..")
        

async def main():
    intents = discord.Intents.default()
    intents.message_content = True

    # Create and run the Discord bot
    app = QApplication(sys.argv)
    event_loop = QEventLoop(app)
    asyncio.set_event_loop(event_loop)

    yt_opener = YouTubeOpener()
    yt_opener.show()

    client = MyClient(intents=intents, yt_opener=yt_opener)

    asyncio.create_task(yt_opener.process_queue())
    
    await client.start('YOUR-BOT-TOKEN')  # Replace with your bot token

    # Start the PyQt5 event loop using the QEventLoop
    await event_loop.run_forever()

if __name__ == "__main__":
    asyncio.run(main())
