# Telegram Group Help Anime Bot

A powerful Telegram bot for anime keyword automation with bulk processing.

## Features
- Keyword auto-reply system
- Bulk keyword addition
- Photo/GIF support
- Admin management
- Data persistence

## Deployment on Render

1. Fork this repository
2. Go to [Render.com](https://render.com)
3. Create a new Web Service
4. Connect your GitHub repository
5. Set environment variables:
   - `BOT_TOKEN`: Your Telegram bot token
   - `ADMIN_IDS`: Comma-separated admin IDs (e.g., `6621572366,-1002892874648`)

## Commands
- `/start` - Show help
- `/rs [keywords] link` - Single keyword
- `/md` - Bulk keywords
- `/list` - Show keywords
- `/photo` - Set photo/GIF
