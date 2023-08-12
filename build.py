import httpx
import pathlib
import re
import datetime
from bs4 import BeautifulSoup

root = pathlib.Path(__file__).parent.resolve()


def formatGMTime(timestamp):
    UTC_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
    timeStr = datetime.datetime.strptime(timestamp, UTC_FORMAT) + datetime.timedelta(hours=2, minutes=30)
    dateStr = timeStr.strftime("%Y-%m-%d")

    return dateStr


def get_events():
    events = httpx.get("https://api.github.com/users/Love-YY/events").json()[:5]
    results = []

    for event in events:
        tempEvent = {}

        if (event["type"] == "WatchEvent"):
            tempEvent["action"] = "*starred*"
            tempEvent["target"] = event["repo"]["name"]
            tempEvent["time"] = formatGMTime(event["created_at"])
            tempEvent["url"] = event["repo"]["url"].replace("api.", "").replace("repos/", "")
        elif (event["type"] == "ReleaseEvent"):
            tempEvent["action"] = "*released*"
            tempEvent["target"] = event["payload"]["release"]["name"]
            tempEvent["time"] = formatGMTime(event["payload"]["release"]["published_at"])
            tempEvent["url"] = event["payload"]["release"]["html_url"]
        elif (event["type"] == "PushEvent"):
            tempEvent["action"] = "*pushed*"
            tempEvent["target"] = event["repo"]["name"]
            tempEvent["time"] = formatGMTime(event["created_at"])
            tempEvent["url"] = event["payload"]["commits"][0]["url"].replace("api.", "").replace("repos/", "")
        elif (event["type"] == "IssuesEvent"):
            tempEvent["action"] = "*" + event["payload"]["action"] + " issue*"
            tempEvent["target"] = event["repo"]["name"]
            tempEvent["time"] = formatGMTime(event["created_at"])
            tempEvent["url"] = event["payload"]["issue"]["url"].replace("api.", "").replace("repos/", "")
        else:
            tempEvent["action"] = "*" + event["type"].replace("Event", "").lower() + "d*"
            tempEvent["target"] = event["repo"]["name"]
            tempEvent["time"] = formatGMTime(event["created_at"])
            tempEvent["url"] = event["repo"]["url"].replace("api.", "").replace("repos/", "")

        results.append(tempEvent)

    return results


def get_blogs():
    html = httpx.get("https://www.flynoodle.xyz/blog/").text
    soup = BeautifulSoup(html, "html.parser")
    soup_all = soup.find_all("div", class_="abstract-item")[:5]

    results = []

    for item in soup_all:
        temp = {}
        temp["title"] = item.find("div", class_="title").get_text()
        temp["url"] = "https://www.flynoodle.xyz" + item.find("a").get("href")
        temp["date"] = item.find("i", class_="reco-date").find("span").get_text()
        results.append(temp)

    return results


def replace_chunk(content, marker, chunk, inline=False):
    r = re.compile(
        r"<!\-\- {} starts \-\->.*<!\-\- {} ends \-\->".format(marker, marker),
        re.DOTALL,
    )
    if not inline:
        chunk = "\n{}\n".format(chunk)
    chunk = "<!-- {} starts -->{}<!-- {} ends -->".format(marker, chunk, marker)
    return r.sub(chunk, content)


if __name__ == "__main__":
    readme = root / "README.md"
    readme_contents = readme.open().read()

    events = get_events()
    events_md = "\n".join(
        ["* {action} <a href={url} target='_blank'>{target}</a> - {time}".format(**item) for item in events]
    )
    rewritten = replace_chunk(readme_contents, "event", events_md)

    entries = get_blogs()
    blogs_md = "\n".join(
        ["* <a href={url} target='_blank'>{title}</a> - {date}".format(**entry) for entry in entries]
    )
    rewritten = replace_chunk(rewritten, "blog", blogs_md)

    time = (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
    time_md = "Automatically updated on " + time
    rewritten = replace_chunk(rewritten, "time", time_md)

    readme.open("w").write(rewritten)