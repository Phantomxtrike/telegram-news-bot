# Script Version: 1.12 (Priming Limit = 1)

# === Import Necessary Libraries ===

import feedparser 
import time      
import logging   
import asyncio   
import threading 
# --- Removed escape_markdown import ---
# from telegram.helpers import escape_markdown 
from flask import Flask 
from telegram import Bot 
# --- Removed ParseMode import ---
# from telegram.constants import ParseMode 
from telegram.error import TelegramError 
from datetime import datetime, timezone 

# --- Configuration Settings ---

TOKEN = "7399702284:AAFveP3avu4PFYNbr_0YUTLwsO6SSdsnzz4" # Use Replit Secrets
CHANNEL_ID = "-1002671533528" # Your target channel ID or username

# --- List of News Sources ---
NEWS_SOURCES = [
    # Existing Feeds
    ("CNA", "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml"),
    ("Mothership", "https://mothership.sg/feed/"),

    # Added Straits Times Feeds
    ("ST World", "https://www.straitstimes.com/news/world/rss.xml"),
    ("ST Business", "https://www.straitstimes.com/news/business/rss.xml"),
    ("ST Life", "https://www.straitstimes.com/news/life/rss.xml"),
    ("ST Opinion", "https://www.straitstimes.com/news/opinion/rss.xml"),
    ("ST Singapore", "https://www.straitstimes.com/news/singapore/rss.xml"),
    ("ST Asia", "https://www.straitstimes.com/news/asia/rss.xml"),
    ("ST Tech", "https://www.straitstimes.com/news/tech/rss.xml"),
    ("ST Multimedia", "https://www.straitstimes.com/news/multimedia/rss.xml"),
    ("ST Newsletter", "https://www.straitstimes.com/news/newsletter/rss.xml"), # Note: Newsletters might not update like regular news

    # Added Business Times Feeds
    ("BT Singapore", "https://www.businesstimes.com.sg/rss/singapore"), 
    ("BT International", "https://www.businesstimes.com.sg/rss/international"),
    ("BT Opinion", "https://www.businesstimes.com.sg/rss/opinion-features"),
    ("BT Companies", "https://www.businesstimes.com.sg/rss/companies-markets"), 
    ("BT Property", "https://www.businesstimes.com.sg/rss/property"),
    ("BT Startups", "https://www.businesstimes.com.sg/rss/startups-tech"),
    ("BT ESG", "https://www.businesstimes.com.sg/rss/esg"),
    ("BT Wealth", "https://www.businesstimes.com.sg/rss/wealth"),
    ("BT Working Life", "https://www.businesstimes.com.sg/rss/working-life"),
    ("BT Lifestyle", "https://www.businesstimes.com.sg/rss/lifestyle"),
    ("BT Events", "https://www.businesstimes.com.sg/rss/events-awards"),
    ("BT Wealth Invest", "https://www.businesstimes.com.sg/rss/wealth-investing"),
    ("BT SGSME", "https://www.businesstimes.com.sg/rss/sgsme"),
    ("BT Top Stories", "https://www.businesstimes.com.sg/rss/top-stories"),
]

# --- Timing and Limits ---
FETCH_INTERVAL_SECONDS = 1800 # 30 minutes 
SEND_DELAY_SECONDS = 5 
# --- UPDATED: How many of the newest articles *per source* to post during the first priming run ---
INITIAL_POST_LIMIT_PER_SOURCE = 1 # Changed from 5 to 1

# --- Global State Variables ---
bot = Bot(token=TOKEN)
posted_links = set() 
app = Flask(__name__)
# Set logging level back to INFO unless debugging needed
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Helper Function for Sorting (Kept in case needed) ---
def get_entry_datetime(entry):
    """Safely get a timezone-aware datetime object from a feed entry for sorting."""
    try:
        ts = time.mktime(entry.published_parsed)
        dt = datetime.fromtimestamp(ts, tz=timezone.utc) 
        return dt
    except AttributeError:
        return datetime.min.replace(tzinfo=timezone.utc) 
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc) 

# --- Asynchronous Bot Logic ---
async def fetch_and_post_news(prime_run=False): 
    """Fetch feeds. If prime_run, post top N newest per source (plain text). If not, post new (plain text)."""
    log_prefix = "[Priming Run]" if prime_run else "[News Check]"
    logger.info(f"{log_prefix} Starting news fetch cycle for {len(NEWS_SOURCES)} sources.")

    posted_links_before_run = posted_links.copy() 
    total_articles_posted_this_run = 0 

    for source_name, feed_url in NEWS_SOURCES:
        await asyncio.sleep(1) # Slight delay between feed fetches
        logger.info(f"{log_prefix} Processing feed: [{source_name}] {feed_url}")
        articles_posted_this_feed_this_run = 0 

        try:
            feed = feedparser.parse(feed_url)
            if feed.bozo:
                logger.warning(f"{log_prefix} [{source_name}] Feed parsing issue (bozo): {getattr(feed, 'bozo_exception', 'Unknown error')}")
                continue 

            for entry in feed.entries: 
                if not hasattr(entry, 'link') or not isinstance(entry.link, str):
                     logger.warning(f"{log_prefix} [{source_name}] Skipping entry with missing or invalid link: {getattr(entry, 'title', 'No Title')}")
                     continue 

                link_was_already_posted = entry.link in posted_links 

                if not link_was_already_posted:
                    posted_links.add(entry.link)
                    if prime_run:
                         logger.info(f"{log_prefix} [{source_name}] Recorded new link: {entry.link}")

                # --- Posting Logic ---
                should_post = False
                message = "" 
                current_parse_mode = None # Sending as plain text

                entry_title = getattr(entry, 'title', 'No Title') 

                if prime_run:
                    # Check if limit for this feed is reached AND link wasn't posted before this script start
                    if articles_posted_this_feed_this_run < INITIAL_POST_LIMIT_PER_SOURCE and not link_was_already_posted:
                        should_post = True
                        message = f"✨ [{source_name}] {entry_title}\n{entry.link}" 
                else: # Normal run
                    # Post if link wasn't known before this cycle started
                    if entry.link not in posted_links_before_run:
                        should_post = True
                        message = f"📰 [{source_name}] {entry_title}\n{entry.link}" 

                # --- Send message if needed ---
                if should_post:
                    logger.info(f"{log_prefix} [{source_name}] Preparing to post article: {entry_title}")
                    try:
                        logger.debug(f"Sending message with parse_mode='{current_parse_mode}':\n{message}") 

                        await bot.send_message(
                            chat_id=CHANNEL_ID, 
                            text=message, 
                            parse_mode=current_parse_mode 
                        )
                        articles_posted_this_feed_this_run += 1
                        total_articles_posted_this_run += 1
                        logger.info(f"{log_prefix} [{source_name}] Posted to Telegram: {entry.link}")
                        await asyncio.sleep(SEND_DELAY_SECONDS) 
                    except TelegramError as e:
                        logger.error(f"{log_prefix} [{source_name}] Telegram Error sending {entry.link}: {e}")
                    except Exception as e:
                        logger.error(f"{log_prefix} [{source_name}] Unexpected error sending {entry.link}: {e}")

            logger.info(f"{log_prefix} [{source_name}] Finished processing feed. Posts this cycle: {articles_posted_this_feed_this_run}")

        except Exception as e:
            logger.error(f"{log_prefix} Error processing feed [{source_name}] ({feed_url}): {e}", exc_info=True) 

    log_suffix = "Priming run complete." if prime_run else f"News check cycle completed. Articles posted this run: {total_articles_posted_this_run}"
    logger.info(f"{log_prefix} {log_suffix} Total unique links known: {len(posted_links)}")


# --- Main Bot Loop ---
async def main_bot_loop():
    """Main asynchronous loop that periodically calls the news fetching function. Includes initial priming."""
    priming_done = False 

    while True:
        try:
            if not priming_done:
                logger.info("Performing initial priming run...")
                await fetch_and_post_news(prime_run=True)
                priming_done = True 
                logger.info(f"Priming complete. {len(posted_links)} links recorded.")
            else:
                await fetch_and_post_news(prime_run=False) 

        except Exception as e:
            logger.error(f"Error in main loop cycle: {e}", exc_info=True) 

        logger.info(f"Sleeping for {FETCH_INTERVAL_SECONDS} seconds...")
        await asyncio.sleep(FETCH_INTERVAL_SECONDS)

# --- Flask Web Server ---
@app.route('/')
def home():
    """Handles pings from UptimeRobot to keep the Repl alive."""
    return "Bot web server is running!"

def run_flask():
  """Runs the Flask web server."""
  app.run(host='0.0.0.0', port=8080) 

# --- Main Execution Block ---
if __name__ == "__main__":
    logger.info("Starting multi-source news bot...")

    logger.info("Starting Flask server in background thread...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True 
    flask_thread.start()

    logger.info("Starting main news checking loop (includes priming on first iteration)...")
    try:
        asyncio.run(main_bot_loop()) 
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")
    except Exception as e:
        logger.critical(f"Bot crashed in main loop: {e}", exc_info=True) 
