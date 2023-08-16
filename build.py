import httpx
import pathlib
import re
import datetime
import os
import shutil
import gevent
from bs4 import BeautifulSoup
from gevent import monkey
from wordcloud import WordCloud


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
    test = r.findall(content)
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

# the coroutine function to request language
def request_language(url, headers):

    return httpx.get(url, headers=headers).json()

# fetch skills from GitHub repositories and juejin.cn
def fetch_skills(limits=50):

    # patch socket and ssl to make httpx support gevent
    monkey.patch_socket()
    monkey.patch_ssl()
    
    languages_frequency = {}
    headers = {"Authorization": "Bearer %s" % TOKEN}
    repos = httpx.get("https://api.github.com/user/repos", headers=headers).json()

    # get GitHub repositories' languages frequency using coroutine
    jobs = []
    for repo in repos:
        coroutine = gevent.spawn(request_language, **{
            "url": repo["languages_url"],
            "headers": headers,
        })
        jobs.append(coroutine)
    
    gevent.joinall(jobs, timeout=5)

    for job in jobs:
        for language in job.value.keys():
            if language in languages_frequency:
                languages_frequency[language] += 1
            else:
                languages_frequency[language] = 1
    
    # get juejin.cn articles' tags frequency
    url = "https://api.juejin.cn/interact_api/v1/digg/query_page?aid=2608&uuid=7202821904003204664&spider=0"
    headers_juejin = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    data = {
        "cursor":"0",
        "user_id": USER,
        "item_type": 2,
        "sort_type": 2
    }

    # get all articles' tags according to the cursor
    end_flag = False
    while end_flag == False:
        res = httpx.post(url, headers=headers_juejin, json=data).json()

        if res["has_more"] == False:
            break

        for item in res["data"]:
            tag_list = item["tags"]
            for tag_item in tag_list:
                tag_name = tag_item["tag_name"]

                tag = transfrom_tags(tag_name)

                if tag != False:
                    if tag in languages_frequency:
                        languages_frequency[tag] += 1
                    else:
                        languages_frequency[tag] = 1

        # limit the latest 50 articles
        if res["has_more"] and int(data["cursor"]) < limits:
            data["cursor"] = res["cursor"]
        else:
            end_flag = True

    return languages_frequency

# transfrom tags to the format of GitHub tags
def transfrom_tags(tag):
    r = re.compile("[\u4e00-\u9fa5]+")
    transfrom_map = {
        "Vue.js": "Vue",
        "React.js": "React"
    }

    if r.match(tag):
        return False
    else:
        if tag in transfrom_map:
            return transfrom_map[tag]
        else:
            return tag

def generate_skill_cloud(languages_frequency):

    file = "skill_cloud"

    wc = WordCloud(
        font_path="./src/Mulled-Wine-Season.otf",
        height=160,
        mode="RGBA",
        background_color=None,
        max_words=1000,
        colormap="BuPu_r"
    )

    wc.generate_from_frequencies(languages_frequency)
    wc.to_file(file + ".png")
    os.unlink("./src/" + file + ".png")
    shutil.move(file + ".png", "./src/")

    return file


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

    # insert skill cloud in markdown file
    file = generate_skill_cloud(fetch_skills())
    skill_cloud_md = "<img src='./src/" + file + ".png' />"
    rewritten = replace_chunk(rewritten, "skill cloud", skill_cloud_md)

    # update time in markdown file
    time = (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
    time_md = "Automatically updated on " + time
    rewritten = replace_chunk(rewritten, "time", time_md)

    readme.open("w").write(rewritten)