"""
Football News RSS Extractor

Fetches football news from RSS feeds (BBC, L'Equipe, Marca, ESPN, etc.)
and indexes them into Elasticsearch for full-text search.

Usage:
    python fetch_football_news.py                  # fetch latest news
    python fetch_football_news.py --no-es          # skip ES indexing
"""
import os
import re
import json
import hashlib
import logging
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from dotenv import load_dotenv
import httpx
from xml.etree import ElementTree as ET

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/news_extraction.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

ES_HOST = os.getenv("ES_HOST", "localhost")
ES_PORT = os.getenv("ES_PORT", "9200")
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
NEWS_DIR = DATA_DIR / "news"
NEWS_DIR.mkdir(parents=True, exist_ok=True)
Path("logs").mkdir(exist_ok=True)

INDEX_NEWS = "football_news"

RSS_FEEDS = [
    {
        "name": "BBC Sport Football",
        "url": "https://feeds.bbci.co.uk/sport/football/rss.xml",
        "language": "en",
        "country": "UK",
        "category": "general",
    },
    {
        "name": "ESPN FC",
        "url": "https://www.espn.com/espn/rss/soccer/news",
        "language": "en",
        "country": "US",
        "category": "general",
    },
    {
        "name": "Sky Sports Football",
        "url": "https://www.skysports.com/rss/12040",
        "language": "en",
        "country": "UK",
        "category": "general",
    },
    {
        "name": "Marca Football",
        "url": "https://e00-marca.uecdn.es/rss/futbol/futbol.xml",
        "language": "es",
        "country": "ES",
        "category": "general",
    },
    {
        "name": "L'Equipe Football",
        "url": "https://dwh.lequipe.fr/api/edito/rss?path=/Football/",
        "language": "fr",
        "country": "FR",
        "category": "general",
    },
    {
        "name": "Guardian Football",
        "url": "https://www.theguardian.com/football/rss",
        "language": "en",
        "country": "UK",
        "category": "general",
    },
    {
        "name": "BBC Sport Premier League",
        "url": "https://feeds.bbci.co.uk/sport/football/premier-league/rss.xml",
        "language": "en",
        "country": "UK",
        "category": "PL",
    },
    {
        "name": "BBC Sport La Liga",
        "url": "https://feeds.bbci.co.uk/sport/football/european-championship/rss.xml",
        "language": "en",
        "country": "UK",
        "category": "european",
    },
]

# Mapping of keywords to canonical team names for article tagging
TEAM_KEYWORDS = {
    # Premier League
    "Arsenal": "Arsenal FC", "Gunners": "Arsenal FC",
    "Aston Villa": "Aston Villa FC", "Villa": "Aston Villa FC",
    "Bournemouth": "AFC Bournemouth",
    "Brentford": "Brentford FC",
    "Brighton": "Brighton & Hove Albion FC",
    "Chelsea": "Chelsea FC", "Blues": "Chelsea FC",
    "Crystal Palace": "Crystal Palace FC", "Palace": "Crystal Palace FC",
    "Everton": "Everton FC", "Toffees": "Everton FC",
    "Fulham": "Fulham FC",
    "Liverpool": "Liverpool FC", "Reds": "Liverpool FC",
    "Luton": "Luton Town FC",
    "Man City": "Manchester City FC", "Manchester City": "Manchester City FC", "City": "Manchester City FC",
    "Man United": "Manchester United FC", "Manchester United": "Manchester United FC", "Man Utd": "Manchester United FC",
    "Newcastle": "Newcastle United FC", "Magpies": "Newcastle United FC",
    "Nottingham Forest": "Nottingham Forest FC", "Forest": "Nottingham Forest FC",
    "Sheffield United": "Sheffield United FC", "Blades": "Sheffield United FC",
    "Tottenham": "Tottenham Hotspur FC", "Spurs": "Tottenham Hotspur FC",
    "West Ham": "West Ham United FC", "Hammers": "West Ham United FC",
    "Wolves": "Wolverhampton Wanderers FC", "Wolverhampton": "Wolverhampton Wanderers FC",
    "Ipswich": "Ipswich Town FC",
    "Leicester": "Leicester City FC", "Foxes": "Leicester City FC",
    "Southampton": "Southampton FC", "Saints": "Southampton FC",
    # La Liga
    "Barcelona": "FC Barcelona", "Barça": "FC Barcelona", "Barca": "FC Barcelona",
    "Real Madrid": "Real Madrid CF", "Madrid": "Real Madrid CF",
    "Atletico Madrid": "Atlético de Madrid", "Atletico": "Atlético de Madrid",
    "Sevilla": "Sevilla FC",
    "Real Sociedad": "Real Sociedad de Fútbol",
    "Real Betis": "Real Betis Balompié", "Betis": "Real Betis Balompié",
    "Villarreal": "Villarreal CF",
    "Athletic Bilbao": "Athletic Club", "Bilbao": "Athletic Club",
    "Valencia": "Valencia CF",
    "Girona": "Girona FC",
    # Ligue 1
    "PSG": "Paris Saint-Germain FC", "Paris Saint-Germain": "Paris Saint-Germain FC", "Paris": "Paris Saint-Germain FC",
    "Marseille": "Olympique de Marseille", "OM": "Olympique de Marseille",
    "Lyon": "Olympique Lyonnais", "OL": "Olympique Lyonnais",
    "Monaco": "AS Monaco FC",
    "Lille": "LOSC Lille", "LOSC": "LOSC Lille",
    "Nice": "OGC Nice",
    "Rennes": "Stade Rennais FC 1901",
    "Lens": "RC Lens",
    "Brest": "Stade Brestois 29",
    "Strasbourg": "RC Strasbourg Alsace",
    "Nantes": "FC Nantes",
    "Montpellier": "Montpellier HSC",
    "Toulouse": "Toulouse FC",
    "Reims": "Stade de Reims",
}

LEAGUE_KEYWORDS = {
    "Premier League": "PL", "EPL": "PL", "English Premier League": "PL",
    "La Liga": "PD", "LaLiga": "PD", "Liga": "PD", "Primera División": "PD",
    "Ligue 1": "FL1", "Ligue1": "FL1",
    "Champions League": "CL", "UCL": "CL",
    "Europa League": "UEL",
    "World Cup": "WC", "Coupe du Monde": "WC",
}


@dataclass
class NewsArticle:
    article_id: str
    title: str
    description: str
    link: str
    published_at: str
    source_name: str
    source_language: str
    source_country: str
    source_category: str
    teams_mentioned: List[str]
    leagues_mentioned: List[str]
    fetched_at: str
    content_text: str = ""  # full text if available


class FootballNewsExtractor:
    """Fetches and parses football news from multiple RSS feeds."""

    def __init__(self):
        self.client = httpx.Client(
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            },
            follow_redirects=True,
        )
        self.stats = {"feeds_processed": 0, "articles_extracted": 0, "errors": 0}

    def _generate_article_id(self, link, title):
        raw = f"{link}|{title}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _detect_teams(self, text):
        """Find team name mentions in text and return canonical names."""
        found = set()
        if not text:
            return []
        # Sort by key length descending so "Manchester United" matches before "Manchester"
        for keyword in sorted(TEAM_KEYWORDS.keys(), key=len, reverse=True):
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                found.add(TEAM_KEYWORDS[keyword])
        return sorted(found)

    def _detect_leagues(self, text):
        """Find league mentions and return their short codes."""
        found = set()
        if not text:
            return []
        for keyword, code in LEAGUE_KEYWORDS.items():
            if keyword.lower() in text.lower():
                found.add(code)
        return sorted(found)

    def _parse_rss_date(self, date_str):
        """Try multiple date formats and return ISO 8601."""
        if not date_str:
            return datetime.now(timezone.utc).isoformat()

        formats = [
            "%a, %d %b %Y %H:%M:%S %z",   # RFC 822
            "%a, %d %b %Y %H:%M:%S GMT",
            "%Y-%m-%dT%H:%M:%S%z",          # ISO 8601
            "%Y-%m-%dT%H:%M:%SZ",
            "%a, %d %b %Y %H:%M:%S",
            "%d %b %Y %H:%M:%S %z",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.isoformat()
            except ValueError:
                continue

        # Fallback
        return datetime.now(timezone.utc).isoformat()

    def _clean_html(self, text):
        if not text:
            return ""
        clean = re.sub(r"<[^>]+>", "", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        # Decode common HTML entities
        clean = clean.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        clean = clean.replace("&quot;", '"').replace("&#39;", "'").replace("&apos;", "'")
        return clean

    def fetch_feed(self, feed_config):
        """Parse a single RSS/Atom feed and return a list of NewsArticle."""
        url = feed_config["url"]
        logger.info(f"Fetching feed: {feed_config['name']} ({url})")

        try:
            response = self.client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch {feed_config['name']}: {e}")
            self.stats["errors"] += 1
            return []

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML for {feed_config['name']}: {e}")
            self.stats["errors"] += 1
            return []

        articles = []

        # Handle both RSS 2.0 (<item>) and Atom (<entry>) formats
        # RSS 2.0
        items = root.findall(".//item")
        if not items:
            # Atom format
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            items = root.findall(".//atom:entry", ns)

        for item in items:
            try:
                # RSS 2.0 fields
                title = self._get_element_text(item, "title")
                description = self._clean_html(self._get_element_text(item, "description"))
                link = self._get_element_text(item, "link")
                pub_date = self._get_element_text(item, "pubDate") or self._get_element_text(item, "published")

                # Atom fallback
                if not title:
                    title = self._get_element_text(item, "{http://www.w3.org/2005/Atom}title")
                if not link:
                    link_el = item.find("{http://www.w3.org/2005/Atom}link")
                    link = link_el.get("href", "") if link_el is not None else ""
                if not description:
                    description = self._clean_html(
                        self._get_element_text(item, "{http://www.w3.org/2005/Atom}summary")
                    )
                if not pub_date:
                    pub_date = self._get_element_text(item, "{http://www.w3.org/2005/Atom}updated")

                if not title:
                    continue

                # Combine title + description for NLP detection
                full_text = f"{title} {description}"

                article = NewsArticle(
                    article_id=self._generate_article_id(link, title),
                    title=title,
                    description=description,
                    link=link,
                    published_at=self._parse_rss_date(pub_date),
                    source_name=feed_config["name"],
                    source_language=feed_config["language"],
                    source_country=feed_config["country"],
                    source_category=feed_config["category"],
                    teams_mentioned=self._detect_teams(full_text),
                    leagues_mentioned=self._detect_leagues(full_text),
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                    content_text=full_text,
                )
                articles.append(article)

            except Exception as e:
                logger.warning(f"Failed to parse article in {feed_config['name']}: {e}")
                continue

        logger.info(f"  Parsed {len(articles)} articles from {feed_config['name']}")
        self.stats["articles_extracted"] += len(articles)
        self.stats["feeds_processed"] += 1
        return articles

    def _get_element_text(self, element, tag):
        el = element.find(tag)
        return el.text.strip() if el is not None and el.text else ""

    def fetch_all_feeds(self):
        all_articles = []
        for feed in RSS_FEEDS:
            articles = self.fetch_feed(feed)
            all_articles.extend(articles)
            time.sleep(1)  # Be polite to feed servers
        logger.info(
            f"Total: {len(all_articles)} articles from {self.stats['feeds_processed']} feeds"
        )
        return all_articles

    def save_to_json(self, articles):
        date_str = datetime.now().strftime("%Y%m%d_%H%M")
        output_path = NEWS_DIR / f"football_news_{date_str}.json"
        data = {
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "article_count": len(articles),
            "sources": list({a.source_name for a in articles}),
            "articles": [asdict(a) for a in articles],
        }
        output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Saved {len(articles)} articles to {output_path}")
        return output_path

    def close(self):
        self.client.close()


# Elasticsearch mapping with football-specific synonym filter
NEWS_INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "football_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding", "football_synonyms"],
                },
                "multilang_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding"],
                },
            },
            "filter": {
                "football_synonyms": {
                    "type": "synonym",
                    "synonyms": [
                        "goal,but,gol",
                        "transfer,transfert,traspaso,signing",
                        "injury,blessure,lesion,injured,blessé",
                        "coach,manager,entraîneur,entrenador",
                        "win,victoire,victoria",
                        "draw,nul,empate",
                        "defeat,loss,défaite,derrota",
                        "champion,titre,title,campeon",
                        "red card,carton rouge,tarjeta roja,expulsion",
                        "penalty,penalti,pénalty",
                        "clean sheet,invicto,invaincu",
                        "hat trick,triplé,triplete",
                        "derby,classico,clásico,classique",
                        "stadium,stade,estadio",
                        "referee,arbitre,árbitro",
                    ],
                }
            },
        },
    },
    "mappings": {
        "properties": {
            "article_id": {"type": "keyword"},
            "title": {
                "type": "text",
                "analyzer": "football_analyzer",
                "fields": {
                    "keyword": {"type": "keyword", "ignore_above": 512},
                    "suggest": {
                        "type": "completion",
                        "analyzer": "multilang_analyzer",
                    },
                },
            },
            "description": {
                "type": "text",
                "analyzer": "football_analyzer",
            },
            "content_text": {
                "type": "text",
                "analyzer": "football_analyzer",
            },
            "link": {"type": "keyword", "index": False},
            "published_at": {"type": "date"},
            "source_name": {"type": "keyword"},
            "source_language": {"type": "keyword"},
            "source_country": {"type": "keyword"},
            "source_category": {"type": "keyword"},
            "teams_mentioned": {"type": "keyword"},
            "leagues_mentioned": {"type": "keyword"},
            "fetched_at": {"type": "date"},
        }
    },
}


def index_news_to_elasticsearch(articles):
    """Bulk-index articles to ES, using article_id as doc ID for dedup."""
    try:
        from elasticsearch import Elasticsearch, helpers
    except ImportError:
        logger.error("elasticsearch package not installed. Skipping indexing.")
        return

    es_url = f"http://{ES_HOST}:{ES_PORT}"
    logger.info(f"Connecting to Elasticsearch at {es_url}")

    try:
        es = Elasticsearch([es_url], request_timeout=60, retry_on_timeout=True, max_retries=3)
        if not es.ping():
            logger.error("Cannot connect to Elasticsearch")
            return
        logger.info("Connected to Elasticsearch")
    except Exception as e:
        logger.error(f"Elasticsearch connection failed: {e}")
        return

    # Create index if not exists
    if not es.indices.exists(index=INDEX_NEWS):
        es.indices.create(index=INDEX_NEWS, body=NEWS_INDEX_MAPPING)
        logger.info(f"Created index '{INDEX_NEWS}' with football analyzer")
    else:
        logger.info(f"Index '{INDEX_NEWS}' already exists")

    # Bulk index with article_id as doc ID (dedup)
    actions = []
    for article in articles:
        doc = asdict(article)
        actions.append({
            "_index": INDEX_NEWS,
            "_id": article.article_id,
            "_source": doc,
        })

    if actions:
        success, errors = helpers.bulk(es, actions, raise_on_error=False)
        logger.info(f"Indexed {success} articles ({len(errors)} errors)")
        if errors:
            for err in errors[:5]:
                logger.warning(f"  Index error: {err}")
    else:
        logger.info("No articles to index")


def search_news(query, filters=None, size=20):
    """Full-text search on football_news index. Returns articles with scores."""
    try:
        from elasticsearch import Elasticsearch
    except ImportError:
        logger.error("elasticsearch package not available")
        return []

    es = Elasticsearch([f"http://{ES_HOST}:{ES_PORT}"], request_timeout=30)
    if not es.ping():
        return []

    # Build query
    must = [
        {
            "multi_match": {
                "query": query,
                "fields": ["title^3", "description^2", "content_text"],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        }
    ]

    filter_clauses = []
    if filters:
        if filters.get("source_language"):
            filter_clauses.append({"term": {"source_language": filters["source_language"]}})
        if filters.get("source_name"):
            filter_clauses.append({"term": {"source_name": filters["source_name"]}})
        if filters.get("teams"):
            filter_clauses.append({"terms": {"teams_mentioned": filters["teams"]}})
        if filters.get("leagues"):
            filter_clauses.append({"terms": {"leagues_mentioned": filters["leagues"]}})
        if filters.get("date_from"):
            filter_clauses.append({"range": {"published_at": {"gte": filters["date_from"]}}})

    body = {
        "query": {
            "bool": {
                "must": must,
                "filter": filter_clauses,
            }
        },
        "size": size,
        "sort": [{"_score": "desc"}, {"published_at": "desc"}],
        "highlight": {
            "fields": {
                "title": {"number_of_fragments": 0},
                "description": {"fragment_size": 200, "number_of_fragments": 2},
            },
            "pre_tags": ["**"],
            "post_tags": ["**"],
        },
    }

    try:
        result = es.search(index=INDEX_NEWS, body=body)
        hits = []
        for hit in result["hits"]["hits"]:
            article = hit["_source"]
            article["_score"] = hit["_score"]
            article["_highlights"] = hit.get("highlight", {})
            hits.append(article)
        return hits
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []


def get_news_stats():
    """Return aggregated stats (by source, language, team, league) from ES."""
    try:
        from elasticsearch import Elasticsearch
    except ImportError:
        return {}

    es = Elasticsearch([f"http://{ES_HOST}:{ES_PORT}"], request_timeout=15)
    if not es.ping():
        return {}

    try:
        count = es.count(index=INDEX_NEWS)["count"]

        # Aggregations
        body = {
            "size": 0,
            "aggs": {
                "by_source": {"terms": {"field": "source_name", "size": 20}},
                "by_language": {"terms": {"field": "source_language", "size": 10}},
                "by_team": {"terms": {"field": "teams_mentioned", "size": 20}},
                "by_league": {"terms": {"field": "leagues_mentioned", "size": 10}},
                "date_range": {
                    "date_range": {
                        "field": "published_at",
                        "ranges": [
                            {"key": "last_24h", "from": "now-1d/d"},
                            {"key": "last_7d", "from": "now-7d/d"},
                            {"key": "last_30d", "from": "now-30d/d"},
                        ],
                    }
                },
            },
        }
        result = es.search(index=INDEX_NEWS, body=body)
        aggs = result["aggregations"]

        return {
            "total_articles": count,
            "sources": {b["key"]: b["doc_count"] for b in aggs["by_source"]["buckets"]},
            "languages": {b["key"]: b["doc_count"] for b in aggs["by_language"]["buckets"]},
            "top_teams": {b["key"]: b["doc_count"] for b in aggs["by_team"]["buckets"]},
            "top_leagues": {b["key"]: b["doc_count"] for b in aggs["by_league"]["buckets"]},
        }
    except Exception as e:
        logger.error(f"Stats query failed: {e}")
        return {}


def main():
    """Main extraction pipeline: fetch RSS → save JSON → index to ES."""
    import argparse

    parser = argparse.ArgumentParser(description="Football News RSS Extractor")
    parser.add_argument("--no-es", action="store_true", help="Skip Elasticsearch indexing")
    args = parser.parse_args()

    extractor = FootballNewsExtractor()

    try:
        articles = extractor.fetch_all_feeds()

        if not articles:
            print("No articles fetched")
            return

        extractor.save_to_json(articles)

        print(f"\nSummary: {len(articles)} articles from {extractor.stats['feeds_processed']} feeds "
              f"({extractor.stats['errors']} errors)")

        all_teams = set()
        for a in articles:
            all_teams.update(a.teams_mentioned)
        if all_teams:
            print(f"Teams mentioned: {', '.join(sorted(all_teams)[:10])}...")

        if not args.no_es:
            index_news_to_elasticsearch(articles)
        else:
            print("Skipping Elasticsearch indexing (--no-es)")

    except Exception as e:
        logger.error(f"News extraction failed: {e}")
        raise
    finally:
        extractor.close()


if __name__ == "__main__":
    main()
