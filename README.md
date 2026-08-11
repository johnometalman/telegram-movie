# Telegram Movie/TV Show Streaming Availability Bot

A Telegram bot that tells you in which countries a movie or TV series is available on your favorite streaming services (Netflix, HBO Max, Amazon Prime Video, Disney+, Apple TV+).

## Features

- 🔍 Search for any movie or TV show
- 🌍 Check availability across 40+ countries
- 📺 Supports major streaming platforms:
  - Netflix
  - HBO Max
  - Amazon Prime Video
  - Disney+
  - Apple TV+
- 🎯 Interactive search with multiple result selection
- 🐳 Docker-based for consistent local and cloud deployment
- 🚀 Easy deployment to Render using Dockerfile

## Prerequisites

- Docker (required for both local and cloud deployment)
- Telegram account
- **Important**: The main bot file must be named `bot.py` - Telegram will not accept connections if the file has a different name. The Dockerfile is configured to run `python bot.py`, so this filename is required.

## Quick Start

This project is designed to work in two ways:
- **Locally using Docker** - for development and testing
- **Deployed on Render using Dockerfile** - for production cloud deployment

### 1. Create Your Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Start a chat with BotFather by sending `/start`
3. Create a new bot by sending `/newbot`
4. Follow the prompts:
   - Choose a name for your bot (e.g., "My Movie Bot")
   - Choose a username for your bot (must end in `bot`, e.g., `my_movie_bot`)
5. BotFather will give you a **bot token** (looks like `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)
6. **Copy this token** - you'll need it for the next step

### 2. Set Up the Project

Clone the repository and navigate to the project directory:

```bash
cd movie-query
```

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit the `.env` file and add your Telegram bot token:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

Replace `your_bot_token_here` with the token you received from BotFather.

### 4. Configure .dockerignore and .gitignore

The project includes `.dockerignore` and `.gitignore` files to exclude unnecessary files from Docker builds and Git commits. Review and modify these files if needed for your Python project:

**.dockerignore** - Excludes files from Docker build context:
- Python cache files (`__pycache__/`, `*.pyc`)
- Virtual environments (`venv/`)
- Environment files (`.env` - security risk)
- OS files (`.DS_Store`)
- Log files (`*.log`)

**.gitignore** - Excludes files from Git repository:
- Same exclusions as .dockerignore
- Ensures sensitive data (tokens, API keys) are never committed

**Important**: Never commit your `.env` file or any files containing sensitive information like bot tokens or API keys.

#### Docker (Recommended)

This is the primary method - use Docker for both local development and cloud deployment. No additional installation needed beyond Docker itself.


### 5. Run the Bot

#### Docker (Recommended)

```bash
docker-compose up -d
```

The bot will start in a container using the same Dockerfile that Render uses for cloud deployment.


### 6. Test Your Bot

1. Open Telegram and search for your bot using the username you chose
2. Start a chat with your bot by sending `/start`
3. Try searching for a movie or TV show, e.g., "Inception" or "Breaking Bad"

## Deployment Options

This project is designed to be deployed **only using Docker** - both for local development and cloud deployment. This ensures consistency across environments and simplifies the deployment process.

### Render (Recommended for Cloud)

Deploy to Render using the Dockerfile - Render will automatically build and run your bot in a container:

[Render](https://render.com) is the easiest way to deploy your bot to the cloud:

1. Create a [Render account](https://render.com) if you don't have one
2. Connect your GitHub repository to Render
3. Create a new **Web Service**:
   - Choose your repository
   - Select "Docker" as the runtime
   - Render will automatically detect your Dockerfile
4. Configure the service:
   - Name: your-bot-name
   - Region: choose a region close to your users
   - Branch: `master` (or your main branch)
5. Add environment variable:
   - Key: `TELEGRAM_BOT_TOKEN`
   - Value: your bot token from BotFather
6. Click "Create Web Service"
7. Render will build and deploy your bot
8. Your bot will be available at `https://your-bot-name.onrender.com`

**Note:** Render free tier services spin down after inactivity. The bot will automatically wake up when it receives a message from Telegram.

### Docker (Local Development)

Run locally using the same Dockerfile that's used for cloud deployment:

```bash
docker-compose up -d
```

To view logs:

```bash
docker-compose logs -f
```

To stop the bot:

```bash
docker-compose down
```

### Other Platforms

The bot can be deployed to any platform that supports Docker containers. Popular options include:
- Heroku (Container Registry)
- Railway
- DigitalOcean App Platform
- AWS ECS
- Google Cloud Run
- Azure Container Instances

**Note**: This project is Docker-only - do not attempt to deploy using non-container methods.

## Configuration

### Environment Variables

- `TELEGRAM_BOT_TOKEN` (required): Your bot token from BotFather

### Docker Configuration

The Dockerfile is configured to run `python bot.py` as the main command. This is why the bot file must be named `bot.py` - changing this filename will break the deployment both locally and on Render.

### Customization

You can customize the bot by editing `bot.py`:

- **Streaming Services**: Modify `USER_SERVICES` and `SERVICE_VARIANTS` to add/remove streaming platforms
- **Countries**: Modify `COUNTRIES` and `COUNTRY_NAMES` to change which regions are checked
- **Search Results**: Adjust the number of search results in the `search()` call

## How It Works

1. The bot uses the JustWatch API to search for movies and TV shows
2. When you search for a title, it finds matching entries
3. For each entry, it checks streaming availability across configured countries
4. It filters results to show only your preferred streaming services
5. Results are formatted and sent back via Telegram

## Troubleshooting

### Bot doesn't respond

- Check that your `.env` file contains the correct token
- Verify the bot is running: `docker-compose ps`
- Check logs: `docker-compose logs -f`
- Make sure you've started a conversation with your bot in Telegram
- **Important**: Ensure the main bot file is named `bot.py` (Telegram requirement)

### Docker issues

- Ensure Docker is running: `docker ps`
- Check logs: `docker-compose logs -f`
- Rebuild container: `docker-compose up -d --build`
- Verify .dockerignore is configured correctly if you're having build issues

### "No results found"

- Try a more specific title
- Check if the title is correctly spelled
- Some very recent releases may not be in the database yet

## Project Structure

```
movie-query/
├── bot.py              # Main bot logic (MUST be named bot.py - Telegram requirement)
├── api/
│   └── index.py       # Vercel serverless endpoint (optional)
├── Dockerfile         # Docker configuration (CMD runs "python bot.py")
├── docker-compose.yml # Docker Compose configuration for local development
├── .dockerignore      # Files to exclude from Docker builds
├── .gitignore         # Files to exclude from Git repository
├── requirements.txt   # Python dependencies
├── .env.example      # Example environment variables
└── README.md         # This file
```

## License

This project is open source and available under the MIT License.

## Contributing

Contributions are welcome! Feel free to submit issues or pull requests.

## Support

If you encounter any issues or have questions, please open an issue on the GitHub repository.
