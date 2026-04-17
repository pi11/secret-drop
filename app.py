import secrets
import string
import re
from datetime import datetime, timedelta
from sanic import Sanic
from sanic.response import html, redirect
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv

load_dotenv()

BOT_PATTERNS = re.compile(
    r"(bot|crawler|spider|crawling|slurp|facebookexternalhit|whatsapp|telegram"
    r"|vkshare|twitterbot|linkedinbot|discordbot|applebot|googlebot|bingbot"
    r"|yandexbot|duckduckbot|baiduspider|sogou|exabot|ia_archiver"
    r"|proximic|seznambot|ahrefsbot|semrushbot|mj12bot|dotbot|petalbot"
    r"|bytespider|gptbot|claudebot|anthropic-ai|ccbot|cohere-ai|perplexity"
    r"|curl|wget|python-requests|go-http-client|java/|apache-httpclient"
    r"|okhttp|libwww|httpx|scrapy)",
    re.IGNORECASE,
)


app = Sanic("secret-share")

jinja = Environment(loader=FileSystemLoader("templates"), autoescape=True)

# In-memory store: slug -> {text, expires_at}
store: dict = {}

SLUG_CHARS = string.ascii_lowercase + string.digits + "-"
SLUG_LENGTH = 8
SECRET_TTL_HOURS = 24


def is_bot(user_agent: str | None) -> bool:
    if not user_agent:
        return True
    return bool(BOT_PATTERNS.search(user_agent))


def make_slug() -> str:
    while True:
        slug = "".join(secrets.choice(SLUG_CHARS) for _ in range(SLUG_LENGTH))
        if slug not in store:
            return slug


def purge_expired():
    now = datetime.utcnow()
    expired = [k for k, v in store.items() if v["expires_at"] < now]
    for k in expired:
        del store[k]


@app.get("/")
async def index(request):
    tmpl = jinja.get_template("index.html")
    return html(tmpl.render())


@app.post("/create")
async def create(request):
    text = request.form.get("secret", "").strip()
    if not text:
        tmpl = jinja.get_template("index.html")
        return html(tmpl.render(error="Secret cannot be empty."), status=400)

    purge_expired()
    slug = make_slug()
    store[slug] = {
        "text": text,
        "expires_at": datetime.utcnow() + timedelta(hours=SECRET_TTL_HOURS),
        "one_time": True,
    }
    link = f"{request.scheme}://{request.host}/s/{slug}"
    tmpl = jinja.get_template("created.html")
    return html(tmpl.render(link=link, slug=slug))


@app.get("/s/<slug>")
async def view_secret(request, slug: str):

    purge_expired()
    entry = store.get(slug)
    if not entry:
        tmpl = jinja.get_template("gone.html")
        return html(tmpl.render(), status=404)

    ua = request.headers.get("User-Agent")
    if is_bot(ua):
        return redirect("/bot")

    text = entry["text"]
    if entry.get("one_time"):
        del store[slug]

    tmpl = jinja.get_template("secret.html")
    return html(tmpl.render(text=text))


@app.get("/bot")
async def bot(request):
    tmpl = jinja.get_template("bot.html")
    return html(tmpl.render())


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8888)),
        workers=int(os.getenv("WORKERS", 1)),
        debug=os.getenv("DEBUG", "false").lower() == "true",
        auto_reload=os.getenv("DEBUG", "false").lower() == "true",
    )
