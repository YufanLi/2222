from __future__ import unicode_literals

import os
import sys
import redis
import requests
from argparse import ArgumentParser
from bs4 import BeautifulSoup
from flask import Flask, request, abort
from linebot import (LineBotApi, WebhookParser)
from linebot.exceptions import (InvalidSignatureError)
from linebot.models import (MessageEvent, TextMessage, TextSendMessage, ImageMessage, VideoMessage, FileMessage,
                            StickerMessage, StickerSendMessage
                            )
from linebot.utils import PY3

# fill in the following.
HOST = "redis-11363.c1.asia-northeast1-1.gce.cloud.redislabs.com"
PWD = "1nOA0St0I7p9pQqu8HkQ18XqDfnoPeoL"
PORT = "11363"

# HOST= "redis-15099.c80.us-east-1-2.ec2.cloud.redislabs.com"
# PWD = "jEE4wHOkCOvOLxXCb21NWYHLlgEGzCch"
# PORT = "15099"
redis1 = redis.Redis(host=HOST, password=PWD, port=PORT)

app = Flask(__name__)

# get channel_secret and channel_access_token from your environment variable
channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)

# obtain the port that heroku assigned to this app.
heroku_port = os.getenv('PORT', None)

if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

line_bot_api = LineBotApi(channel_access_token)
parser = WebhookParser(channel_secret)

# news source url
news_url = r'https://hk.news.yahoo.com/topic/coronavirus'


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # parse webhook body
    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        abort(400)

    # if event is MessageEvent and message is TextMessage, then echo text
    for event in events:
        if not isinstance(event, MessageEvent):
            continue
        if isinstance(event.message, TextMessage):
            # todo: 针对不同的文本输入进行不同的反应
            handle_TextMessage(event)
        if isinstance(event.message, ImageMessage):
            handle_ImageMessage(event)
        if isinstance(event.message, VideoMessage):
            handle_VideoMessage(event)
        if isinstance(event.message, FileMessage):
            handle_FileMessage(event)
        if isinstance(event.message, StickerMessage):
            handle_StickerMessage(event)

        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessage):
            continue

    return 'OK'


# todo: 当缓存的新闻数据不是最新的时候，获取最新的新闻数据，反之则直接返回缓存的新闻数据
def get_hotNews():
    if redis1.ttl('hot_news') < 0:
        news_list = crawl_hotNews()
        for new in news_list:
            redis1.sadd("hot_news", new)
        redis1.expire("hot_news", 21600)
    return redis.smembers('hot_news')


# todo: 返回当前热点的新闻
def crawl_hotNews():
    # 爬取热点新闻数据 然后缓存在redis 中

    # 获取html 界面
    webPage = requests.get(news_url)
    bs = BeautifulSoup(webPage.text, 'lxml')

    news_list = bs.find_all('div', {'class': 'Pos(r)'})
    hot_news = []
    for new in news_list:
        new_pic_obj = new.find('img', {'class': 'Trsdu(.42s)'})
        new_pic_url = new_pic_obj['src']
        new_title_obj = new.find('div', {'class': 'Fz(20px)'})
        new_title_txt = new_title_obj.get_text()
        new_link = new.find('a')
        new_link_url = new_link['href']
        hot_news.append([new_pic_url, new_title_txt, new_link_url])
    return hot_news


# Handler function for Text Message
def handle_TextMessage(event):
    if 'hot news' == event.message.text:
        # 调用获取最新新闻的接口获取新闻

        hot_news = get_hotNews()
        message = TemplateSendMessage(
            alt_text='Hot news about the coronavirus',
            template=CarouselTemplate(
                columns=[
                    CarouselColumn(
                        thumbnail_image_url=hot_news[0][0],
                        title=hot_news[0][1],
                        text=hot_news[0][1],
                        actions=[
                            URIAction(uri=hot_news[0][2], label='label')
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url=hot_news[1][0],
                        title=hot_news[1][1],
                        text=hot_news[1][1],
                        actions=[
                            URIAction(uri=hot_news[1][2], label='label')
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url=hot_news[2][0],
                        title=hot_news[2][1],
                        text=hot_news[2][1],
                        actions=[
                            URIAction(uri=hot_news[2][2], label='label')
                        ]
                    )
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            message
        )

    print(event.message.text)
    msg = 'You said: "' + event.message.text + '" '
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(msg)
    )


# Handler function for Sticker Message
def handle_StickerMessage(event):
    line_bot_api.reply_message(
        event.reply_token,
        StickerSendMessage(
            package_id=event.message.package_id,
            sticker_id=event.message.sticker_id)
    )


# Handler function for Image Message
def handle_ImageMessage(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="Nice image!")
    )


# Handler function for Video Message
def handle_VideoMessage(event):
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="Nice video!"))


# Handler function for File Message
def handle_FileMessage(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="Nice file!")
    )


if __name__ == "__main__":
    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-d', '--debug', default=False, help='debug')
    options = arg_parser.parse_args()

    app.run(host='0.0.0.0', debug=options.debug, port=heroku_port)

# {
#   "type": "template",
#   "altText": "this is a carousel template",
#   "template": {
#       "type": "carousel",
#       "columns": [
#           {
#             "thumbnailImageUrl": "https://example.com/bot/images/item1.jpg",
#             "imageBackgroundColor": "#FFFFFF",
#             "title": "this is menu",
#             "text": "description",
#             "defaultAction": {
#                 "type": "uri",
#                 "label": "View detail",
#                 "uri": "http://example.com/page/123"
#             },
#             "actions": [
#                 {
#                     "type": "postback",
#                     "label": "Buy",
#                     "data": "action=buy&itemid=111"
#                 },
#                 {
#                     "type": "postback",
#                     "label": "Add to cart",
#                     "data": "action=add&itemid=111"
#                 },
#                 {
#                     "type": "uri",
#                     "label": "View detail",
#                     "uri": "http://example.com/page/111"
#                 }
#             ]
#           },
#           {
#             "thumbnailImageUrl": "https://example.com/bot/images/item2.jpg",
#             "imageBackgroundColor": "#000000",
#             "title": "this is menu",
#             "text": "description",
#             "defaultAction": {
#                 "type": "uri",
#                 "label": "View detail",
#                 "uri": "http://example.com/page/222"
#             },
#             "actions": [
#                 {
#                     "type": "postback",
#                     "label": "Buy",
#                     "data": "action=buy&itemid=222"
#                 },
#                 {
#                     "type": "postback",
#                     "label": "Add to cart",
#                     "data": "action=add&itemid=222"
#                 },
#                 {
#                     "type": "uri",
#                     "label": "View detail",
#                     "uri": "http://example.com/page/222"
#                 }
#             ]
#           }
#       ],
#       "imageAspectRatio": "rectangle",
#       "imageSize": "cover"
#   }
# }
