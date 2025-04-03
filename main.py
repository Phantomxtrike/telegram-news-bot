# Script Version: 1.15 (Updated Filter Keywords)

# === Import Necessary Libraries ===

import feedparser 
import time      
import logging   
import asyncio   
import threading 
from flask import Flask 
from telegram import Bot 
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
    # ("Today Online", "https://www.todayonline.com/rss"), # Removed previously
    
    # Added Straits Times Feeds
    ("ST World", "https://www.straitstimes.com/news/world/rss.xml"),
    ("ST Business", "https://www.straitstimes.com/news/business/rss.xml"),
    ("ST Life", "https://www.straitstimes.com/news/life/rss.xml"),
    ("ST Opinion", "https://www.straitstimes.com/news/opinion/rss.xml"),
    ("ST Singapore", "https://www.straitstimes.com/news/singapore/rss.xml"),
    ("ST Asia", "https://www.straitstimes.com/news/asia/rss.xml"),
    ("ST Tech", "https://www.straitstimes.com/news/tech/rss.xml"),
    ("ST Multimedia", "https://www.straitstimes.com/news/multimedia/rss.xml"),
    ("ST Newsletter", "https://www.straitstimes.com/news/newsletter/rss.xml"), 
    
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

# --- Keyword Filtering ---
# Add keywords here (case-insensitive). Only articles with titles containing
# at least one of these keywords will be posted.
# Leave the list empty [] to disable filtering and post all news.
# --- UPDATED Keywords ---
FILTER_KEYWORDS = [
    "mediacorp", 
    "mewatch", 
    "melisten", 
    # Add more keywords as needed, separated by commas
] 

# --- Timing and Limits ---
FETCH_INTERVAL_SECONDS = 1800 # 30 minutes 
SEND_DELAY_SECONDS = 5 
INITIAL_POST_LIMIT_PER_SOURCE = 1 

# --- Global State Variables ---
bot = Bot(token=TOKEN)
posted_links = set() 
app = Flask(__name__)
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
    """Fetch feeds. If prime_run, post top N newest per source (plain text). If not, post new (plain text). Applies keyword filter."""
    log_prefix = "[Priming Run]" if prime_run else "[News Check]"
    logger.info(f"{log_prefix} Starting news fetch cycle for {len(NEWS_SOURCES)} sources.")
    
    posted_links_before_run = posted_links.copy() 
    total_articles_posted_this_run = 0 

    # Convert filter keywords to lowercase once for efficiency
    filter_keywords_lower = [kw.lower() for kw in FILTER_KEYWORDS]

    for source_name, feed_url in NEWS_SOURCES:
        await asyncio.sleep(1) 
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
                entry_title = getattr(entry, 'title', 'No Title') 
                title_lower = entry_title.lower() # Lowercase title for case-insensitive matching

                # --- Keyword Check ---
                keywords_found = False
                if not filter_keywords_lower: 
                    keywords_found = True
                else:
                    if any(keyword in title_lower for keyword in filter_keywords_lower):
                        keywords_found = True
                
                # Record link only if it's truly new
                if not link_was_already_posted:
                    posted_links.add(entry.link)
                    if prime_run:
                         logger.info(f"{log_prefix} [{source_name}] Recorded new link: {entry.link}")

                # --- Posting Logic ---
                should_post = False
                message = "" 
                current_parse_mode = None 

                # Only proceed if keywords are found (or filtering is disabled)
                if keywords_found:
                    if prime_run:
                        if articles_posted_this_feed_this_run < INITIAL_POST_LIMIT_PER_SOURCE and not link_was_already_posted:
                            should_post = True
                            message = f"✨ [{source_name}] {entry_title}\n{entry.link}" 
                    else: # Normal run
                        if entry.link not in posted_links_before_run:
                            should_post = True
                            message = f"📰 [{source_name}] {entry_title}\n{entry.link}" 
                # Log if filtered out (and was new)
                elif not link_was_already_posted: 
                     logger.info(f"{log_prefix} [{source_name}] Skipping article (keywords not found): {entry_title}")


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
  # Check if Flask app object exists
  if app:
      app.run(host='0.0.0.0', port=8080) 
  else:
      logger.error("Flask app object not initialized.")

# --- Main Execution Block ---
if __name__ == "__main__":
    # Setup logger first
    logger.info("Starting multi-source news bot...")

    # Check essential config before proceeding (Token/Channel ID check from v1.14)
    if not TOKEN or not CHANNEL_ID:
        logger.critical("TOKEN or CHANNEL_ID missing in environment variables. Cannot start.")
        exit()
    elif not bot:
         logger.critical("Bot initialization failed (likely missing TOKEN). Cannot start.")
         exit()
    else:
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
