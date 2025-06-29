class Bot(Client):
    def __init__(self):
        super().__init__(
            name="codeflixbots",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            workers=200,
            plugins={"root": "plugins"},
            sleep_threshold=15,
        )
        self.start_time = time.time()

    async def start(self):
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), 'plugins'))
        await super().start()
        me = await self.get_me()
        self.mention = me.mention
        self.username = me.username
        self.uptime = Config.BOT_UPTIME
        if Config.WEBHOOK:
            app = web.AppRunner(await web_server())
            await app.setup()
            port = int(os.environ.get("PORT", 8585))
            await web.TCPSite(app, "0.0.0.0", port).start()
        print(f"{me.first_name} Is Started.....✨️")
        # Rest of the start method...
