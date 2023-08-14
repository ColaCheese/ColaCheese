import httpx
import pathlib
import re
import datetime
import os
from bs4 import BeautifulSoup

# root directory of the env
root = pathlib.Path(__file__).parent.resolve()

# get the github token and user id
TOKEN = os.environ.get("ACCESS_TOKEN", "")
USER = os.environ.get("USER", "")

# transfrom UTC timestamp to UTC+8
def formatUTCTime(timestamp):

    UTC_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
    timeStr = datetime.datetime.strptime(timestamp, UTC_FORMAT) + datetime.timedelta(hours=8)
    dateStr = timeStr.strftime("%Y-%m-%d")

    return dateStr

# replace the content between the markers with the new content
def replace_chunk(content, marker, chunk, inline=False):

    r = re.compile(
        r"<!\-\- {} starts \-\->.*<!\-\- {} ends \-\->".format(marker, marker),
        re.DOTALL,
    )
    if not inline:
        chunk = "\n{}\n".format(chunk)
    chunk = "<!-- {} starts -->{}<!-- {} ends -->".format(marker, chunk, marker)
    return r.sub(chunk, content)

# fetch recent 5 events from github as auenthicated user
def fetch_events():

    event_emoji = {
        "CommitCommentEvent": "💬",
        "CreateEvent": "📝",
        "DeleteEvent": "🗑",
        "ForkEvent": "🍴",
        "GollumEvent": "📖",
        "IssueCommentEvent": "🗣",
        "IssuesEvent": "🐛",
        "MemberEvent": "👥",
        "PublicEvent": "🌎",
        "PullRequestEvent": "🔧",
        "PullRequestReviewEvent": "👀",
        "PullRequestReviewCommentEvent": "💬",
        "PullRequestReviewThreadEvent": "💬",
        "PushEvent": "🚀",
        "ReleaseEvent": "🎉",
        "SponsorshipEvent": "🎉",
        "WatchEvent": "⭐️",
    }

    results = []

    headers = {"Authorization": "Bearer %s" % TOKEN}
    events = httpx.get("https://api.github.com/users/ColaCheese/events", headers=headers).json()[:5]
    
    for event in events:
        event_item = {}

        # split pascal case type name to a list, and remove "event"
        type_name_list = re.sub( r"([A-Z])", r" \1", event["type"]).split()
        type_name_list.pop()
        action = "*" + " ".join(type_name_list) + "*"

        # modify results
        event_item["action"] = action
        event_item["time"] = formatUTCTime(event["created_at"])
        event_item["target"] = event["repo"]["name"]
        event_item["url"] = event["repo"]["url"].replace("api.", "").replace("repos/", "")
        event_item["emoji"] = event_emoji[event["type"]]

        results.append(event_item)

    return results

# fetch latest five posted articles in juejin.cn
def fetch_blogs():

    results = []

    html = httpx.get("https://juejin.cn/user/" + USER + "/posts").text
    soup = BeautifulSoup(html, "html.parser")
    soup_all = soup.find_all("li", attrs={"data-growing-title": "entryList"}, limit=5)

    for item in soup_all:
        temp = {}
        temp["title"] = item.find("div", class_="title-row").get_text().strip()
        temp["url"] = "https://juejin.cn" + item.find("a").get("href")
        temp["date"] = item.find("li", class_="item date").get_text().strip()
        results.append(temp)

    return results

# fetch latest five starred articles in juejin.cn
def fetch_stars():

    results = []

    html = httpx.get("https://juejin.cn/user/" + USER + "/likes").text
    soup = BeautifulSoup(html, "html.parser")
    soup_all = soup.find_all("li", attrs={"data-growing-title": "entryList"}, limit=5)

    for item in soup_all:
        temp = {}
        temp["title"] = item.find("div", class_="title-row").get_text().strip()
        temp["url"] = "https://juejin.cn" + item.find("a").get("href")
        results.append(temp)

    return results

# fetch skills from GitHub repositories and juejin.cn
def fetch_skills():

    languages_frequency = {}

    headers = {"Authorization": "Bearer %s" % TOKEN}
    repos = httpx.get("https://api.github.com/user/repos", headers=headers).json()

    # get GitHub repositories' languages frequency
    for repo in repos:
        if repo["language"] is not None:
            if repo["language"] in languages_frequency:
                languages_frequency[repo["language"]] += 1
            else:
                languages_frequency[repo["language"]] = 1
    
    # get juejin.cn articles' tags frequency
    html = httpx.get("https://juejin.cn/user/" + USER + "/likes").text
    soup = BeautifulSoup(html, "html.parser")
    soup_all = soup.find_all("li", attrs={"data-growing-title": "entryList"}, limit=30)

    for item in soup_all:
        tag_list = item.find_all("a", class_="footer-tag")
        for tag_item in tag_list:
            tag = tag_item.get_text().strip()
            if tag in languages_frequency:
                languages_frequency[tag] += 1
            else:
                languages_frequency[tag] = 1

    return results


if __name__ == "__main__":

    readme = root / "README.md"
    readme_contents = readme.open().read()

    # load events in markdown file
    events = fetch_events()
    events_md = "\n".join(
        ["* {emoji} {action} <a href={url} target='_blank'>{target}</a> - {time}".format(**item) for item in events]
    )
    rewritten = replace_chunk(readme_contents, "event", events_md)

    # load blogs in markdown file
    entries = fetch_blogs()
    blogs_md = "\n".join(
        ["* <a href={url} title='{title}' target='_blank'>{title}</a> - {date}".format(**entry) for entry in entries]
    )
    rewritten = replace_chunk(rewritten, "blog", blogs_md)

    # load likes in markdown file
    entries = fetch_stars()
    stars_md = "\n".join(
        ["* <a href={url} title='{title}' target='_blank'>{title}</a>".format(**entry) for entry in entries]
    )
    rewritten = replace_chunk(rewritten, "star", stars_md)

    # insert skills in markdown file
    # fetch_skills()

    # update time in markdown file
    time = (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
    time_md = "Automatically updated on " + time
    rewritten = replace_chunk(rewritten, "time", time_md)

    readme.open("w").write(rewritten)