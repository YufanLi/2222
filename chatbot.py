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
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    TemplateSendMessage, ConfirmTemplate, MessageAction,
    ButtonsTemplate, ImageCarouselTemplate, ImageCarouselColumn, URIAction,
    PostbackAction, DatetimePickerAction,
    CameraAction, CameraRollAction, LocationAction,
    CarouselTemplate, CarouselColumn, PostbackEvent,
    StickerMessage, StickerSendMessage, LocationMessage, LocationSendMessage,
    ImageMessage, VideoMessage, AudioMessage, FileMessage,
    UnfollowEvent, FollowEvent, JoinEvent, LeaveEvent, BeaconEvent,
    MemberJoinedEvent, MemberLeftEvent,
    FlexSendMessage, BubbleContainer, ImageComponent, BoxComponent,
    TextComponent, SpacerComponent, IconComponent, ButtonComponent,
    SeparatorComponent, QuickReply, QuickReplyButton,
    ImageSendMessage,VideoSendMessage,PostbackTemplateAction,
    MessageTemplateAction,URITemplateAction
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
news_url = r'https://www.foxnews.com/category/health/infectious-disease/coronavirus'


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
            if(isinstance(event.message,TextMessage) and event.message.text.lower()=='hospitals'):
                handler_function3(event)
            else:
                handle_TextMessage(event)
        if isinstance(event.message, ImageMessage):
            handle_ImageMessage(event)
        if isinstance(event.message, VideoMessage):
            handle_VideoMessage(event)
        if isinstance(event.message, FileMessage):
            handle_FileMessage(event)
        if isinstance(event.message, StickerMessage):
            handle_StickerMessage(event)
        if(isinstance(event,PostbackEvent) and event.postback.data[0:5]=='prov_'):
            handler_CityList(event)

        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessage):
            continue

    return 'OK'


# todo: 当缓存的新闻数据不是最新的时候，获取最新的新闻数据，反之则直接返回缓存的新闻数据
# createby: LI Yufan
def get_hotNews():
    if redis1.ttl('hot_news') < 0:
        news_list = crawl_hotNews()
        for new in news_list:
            redis1.sadd("hot_news_link", new[0])
            redis1.sadd("hot_news_img", new[1])
            redis1.sadd("hot_news_title", new[2])
            redis1.sadd("hot_news_intro", new[3])
        redis1.expire("hot_news_link", 21600)
        redis1.expire("hot_news_title", 21600)
        redis1.expire("hot_news_img", 21600)
        redis1.expire("hot_news_intro", 21600)

    hot_news_link = redis1.smembers('hot_news_link')
    hot_news_img = redis1.smembers('hot_news_img')
    hot_news_title = redis1.smembers('hot_news_title')
    hot_news_intro = redis1.smembers('hot_news_intro')
    return [list(hot_news_link),list(hot_news_img),list(hot_news_title),list(hot_news_intro)]


# todo: 返回当前热点的新闻
# createby: LI Yufan
def crawl_hotNews():
    # 爬取热点新闻数据 然后缓存在redis 中

    # 获取html 界面
    webPage = requests.get(news_url)
    bs = BeautifulSoup(webPage.text, 'lxml')

    news_layout = bs.find('div',{'class':'article-list'})
    news_list = news_layout.find_all('article', {'class': 'article'})
    hot_news = []
    for news in news_list:
        img_obj = news.find('div',{'class':'m'})
        link = img_obj.find('a')
        imgUrl = img_obj.find('img')
        content_obj = news.find('div',{'class':'info'})
        title = content_obj.find('a')
        content = content_obj.find('p',{'class':'dek'})

        title_text = title.get_text()
        if len(title_text )> 38:
            title_text = title_text[0:37]
            title_text += '..'
        content_text = content.get_text()
        if len(content_text )>38:
            content_text = content_text[0:37]
            content_text+='..'
        link_addr = ''
        if 'video' in link['href']:
            link_addr = link['href']
        else:
            link_addr = 'https://www.foxnews.com'+link['href']
        hot_news.append([link_addr,imgUrl['src'],title_text,content_text])
    return hot_news

# Handler function for Text Message
def handle_TextMessage(event):
    # createby: LI Yufan
    if 'news' == event.message.text.lower():
        # 调用获取最新新闻的接口获取新闻
        hot_news = get_hotNews()
        message = TemplateSendMessage(
            alt_text='Hot news about the coronavirus',
            template=CarouselTemplate(
                columns=[
                    CarouselColumn(
                        thumbnail_image_url=str(hot_news[1][0],encoding='utf-8'),
                        title=str(hot_news[2][0],encoding='utf-8'),
                        text=str(hot_news[3][0],encoding='utf-8'),
                        actions=[
                            URIAction(uri=str(hot_news[0][0],encoding='utf-8'), label='View Detail')
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url=str(hot_news[1][1],encoding='utf-8'),
                        title=str(hot_news[2][1], encoding='utf-8'),
                        text=str(hot_news[3][1], encoding='utf-8'),
                        actions=[
                            URIAction(uri=str(hot_news[0][1], encoding='utf-8'), label='View Detail')
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url=str(hot_news[1][1], encoding='utf-8'),
                        title=str(hot_news[2][2], encoding='utf-8'),
                        text=str(hot_news[3][2], encoding='utf-8'),
                        actions=[
                            URIAction(uri=str(hot_news[0][2], encoding='utf-8'), label='View Detail')
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url=str(hot_news[1][3], encoding='utf-8'),
                        title=str(hot_news[2][3], encoding='utf-8'),
                        text=str(hot_news[3][3], encoding='utf-8'),
                        actions=[
                            URIAction(uri=str(hot_news[0][3], encoding='utf-8'), label='View Detail')
                        ]
                    ),
                    CarouselColumn(
                        thumbnail_image_url=str(hot_news[1][4], encoding='utf-8'),
                        title=str(hot_news[2][4], encoding='utf-8'),
                        text=str(hot_news[3][4], encoding='utf-8'),
                        actions=[
                            URIAction(uri=str(hot_news[0][4], encoding='utf-8'), label='View Detail')
                        ]
                    )
                ]
            )
        )
        line_bot_api.reply_message(
            event.reply_token,
            message
        )
    # createby: Zhang Mingxuan
    else:
        str_prevent_virus = "abcABC*?//"
        if event.message.text == 'Q&A':
            msg = 'OK! '
        elif 'how' in event.message.text.lower() or 'prevention' in event.message.text.lower():
            # elif event.message.text == 'How to prevent the coronary pneumonia?':
            msg = 'Wash hands '
        elif 'what' in event.message.text.lower() or 'outside' in event.message.text.lower():
            # elif event.message.text == 'What should you do during an outbreak?':
            msg = 'Wearing a mask '
        # modifiedBy LI Yufan
        else:
            msg = 'Sorry, for technical reasons, we cannot further provide u other kind of service! Please enter the ' \
                  'command as follow \n \'news\' \t view the latest news of coronavirus topic' \
                  '\n \'Q&A\' \t start Q&A and get answer if we have made it' \
                  '\n \'Q&A\' \t start Q&A and get answer if we have made it' \
                  '\n \'hospitals\' \t view the list of designated hospitals'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(msg)
        )
#data/variable initiated by GAO Han
#province list
init_data=[
    "Anhui","Beijing","Chongqing","Fujian","Gansu","Guangdong","Guangxi","Guizhou","Hainan","Hebei","Henan","Heilongjiang",
    "Hubei","Hunan","Nei Mongolia","Jilin","Jiangsu","Jiangxi","Ningxia","Qinghai","Shandong","Shanxi","Shaanxi",
    "Shanghai","Sichuan","Tianjin","Tibet","Xinjiang","Yunnan","Zhejiang"
]
#province content array
prov_cont_array=[]
#data init end

#Generate province content array
#by GAO Han
def prov_ListArray(arr):
    default_action={'type':'postback','label':"default_label",'data':"default_data"}
    default_content={'type':'button',"style":"secondary","height":"sm","margin":"xs"}
    for item in arr:
        prov_item='prov_'+item
        default_action['label']=item
        default_action['data']=prov_item
        default_content['action']=default_action
        content_str=str(default_content)
        dict_temp=eval(content_str)
        prov_cont_array.append(dict_temp)
    return prov_cont_array

#Handle function3--display info about designated hospitals
#step1--display all the provinces/municipality
#by GAO Han
def handler_function3(event):
    con=prov_ListArray(init_data)
    line_bot_api.reply_message(
        event.reply_token,
        FlexSendMessage(
            alt_text="list",
            contents={
                "type": "bubble",
                "body": {
                "type": "box",
                "layout": "vertical",
                "contents":con
                }
            }
        )
    )

#display city list
#by GAO Han
def handler_CityList(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage("Please choose cities in "+event.postback.data[5:])
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


