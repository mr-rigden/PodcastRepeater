import argparse
from io import BytesIO
import json
import logging
import os
from urllib.parse import urlparse


from jinja2 import Environment, FileSystemLoader
from markdown import markdown
from PIL import Image
import requests
from slugify import slugify
import xmltodict
import yaml


log_format = "%(message)s"
logging.basicConfig(level=logging.INFO, format=log_format)
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description="A little program turns podcast feed into a website")
parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
parser.add_argument("config", help="Config file for podcast", type=str)
args = parser.parse_args()


logger.debug("Initializing Program")



def make_site(config):
    template_env = Environment(loader=FileSystemLoader('templates'))
    theme_env = Environment(loader=FileSystemLoader(config['theme_dir']))

    make_dirs(config['output_dir'])

    podcast = download_and_parse_feed(config['feed_URL'])
    try:
        episodes = process_episodes(podcast)
    except KeyError:
        episodes = []
    download_audio_files(config, episodes)
    download_and_resize_cover_image(config['output_dir'], podcast['rss']['channel']['itunes:image']['@href'])

    render_sitemap(config, episodes, template_env)
    render_front_page(config, episodes, podcast, theme_env)
    render_episodes(config, episodes, podcast, theme_env)


def process_episodes(podcast):
    logger.debug('  Processing episodes')
    episodes = []
    for item in podcast['rss']['channel']['item']:
        if 'enclosure' in item:
            item['url'] = item['enclosure']['@url']
            item['slug'] = slugify(item['title'])
            item['description'] = markdown(item['description'], extensions=["mdx_linkify"])
            url_path = urlparse(item['url']).path
            item['file_name'] = os.path.basename(url_path)
            episodes.append(item)
    return episodes




def download_and_parse_feed(url):
    logger.debug('  Downloading RSS Feed') 
    r = requests.get(url)
    logger.debug('  Parsing XML') 
    podcast = xmltodict.parse(r.text)
    return podcast

def download_audio_files(config, episodes):
    logger.debug('  Downloading episode files')
    for episode in episodes:
        logger.debug('          Downloading episode file')
        file_path = os.path.join(config['output_dir'], 'audio', episode['file_name'])
        if not os.path.exists(file_path):
            r = requests.get(episode['enclosure']['@url'], allow_redirects=True)
            open(file_path, 'wb').write(r.content)


def download_and_resize_cover_image(output_dir, cover_art_url):
    logger.debug('  Downloading cover art')
    cover_art_path = os.path.join(output_dir, "cover_art.jpg")
    small_cover_art_path = os.path.join(output_dir, "small_cover_art.jpg")

    if os.path.exists(cover_art_path):
        return

    response = requests.get(cover_art_url)
    img = Image.open(BytesIO(response.content))
    img.save(cover_art_path)
    img.thumbnail((1000, 1000))
    img.save(small_cover_art_path, optimize=True)


def get_config(file_path):
    logger.debug('Loading config file')
    with open(file_path) as f:
        config = json.loads(f.read())
    return config



def make_dirs(output_dir):
    logger.debug('  Making directories')
    dirs = ['audio', 'episode']
    for dir in dirs:
        dir_path = os.path.join(output_dir, dir)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)


def render_episodes(config, episodes, podcast, theme_env):
    logger.debug('      Rendering episodes')
    for episode in episodes:
        logger.debug('          Rendering episode')
        episode_dir = os.path.join(config['output_dir'], 'episode', episode['slug'])
        if not os.path.exists(episode_dir):
            os.makedirs(episode_dir)
        episode_path = os.path.join(episode_dir, "index.html")
        template = theme_env.get_template('episode.html')
        output = template.render(config=config, episode=episode, podcast=podcast)
        with open(episode_path, 'w') as f:
            f.write(output)


def render_front_page(config, episodes, podcast, theme_env):
    logger.debug('  Rendering front page')
    frontpage_path = os.path.join(config['output_dir'], "index.html")
    template = theme_env.get_template('frontpage.html')
    output = template.render(config=config, episodes=episodes, podcast=podcast)
    with open(frontpage_path, 'w') as f:
        f.write(output)    

def render_sitemap(config, episodes, template_env):
    file_path = os.path.join(config['output_dir'], "sitemap.xml")
    template = template_env.get_template('sitemap.xml')
    output = template.render(config=config, episodes=episodes)
    with open(file_path, 'w') as f:
        f.write(output)

if __name__ == "__main__":
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    config = get_config(args.config)
    make_site(config)
