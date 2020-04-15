from __future__ import unicode_literals

import os
import sys
import redis
import requests
import time
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET
from argparse import ArgumentParser
from bs4 import BeautifulSoup
import http.client
import hashlib
import urllib
import random
import json
from flask import Flask, request, abort
from linebot import (LineBotApi, WebhookParser)
from linebot.exceptions import (InvalidSignatureError,LineBotApiError)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    TemplateSendMessage, ConfirmTemplate, MessageAction,
    ButtonsTemplate, ImageCarouselTemplate, ImageCarouselColumn, URIAction,
    PostbackAction, DatetimePickerAction,
    CameraAction, CameraRollAction, LocationAction,
    CarouselTemplate, CarouselColumn, PostbackEvent,
    StickerMessage, StickerSendMessage, LocationMessage, LocationSendMessage,
    ImageMessage, VideoMessage, AudioMessage, FileMessage,
    FlexSendMessage, BubbleContainer, ImageComponent, BoxComponent,
    TextComponent, SpacerComponent, IconComponent, ButtonComponent,
    SeparatorComponent, QuickReply, QuickReplyButton,
    ImageSendMessage,VideoSendMessage,PostbackTemplateAction,
    MessageTemplateAction
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
# parse xml
tree = ET.ElementTree(file='citylist.xml')
root=tree.getroot()
# baidu translate api
appid = '20200325000404841'
secretKey = 'eOODHG9LnG1nynL0Yd_f'
httpClient = None
initurl = '/api/trans/vip/translate'

fromLang = 'auto'   #原文语种
toLang = 'en'   #译文语种
salt = random.randint(32768, 65536)
lang_lib={'zh':'简体中文','en':'英语','jp':'日语','kor':'韩语','fra':'法语','spa':'西班牙语','th':'泰语','ara':'阿拉伯语','ru':'俄语','pt':'葡萄牙语','de':'德语',
          'it':'意大利语','el':'希腊语','nl':'荷兰语','cht':'繁体中文'}

#translate common words
#created By GAO Han
def langTrans(q):
    sign = appid + q + str(salt) + secretKey
    sign = hashlib.md5(sign.encode()).hexdigest()
    myurl = initurl + '?appid=' + appid + '&q=' + urllib.parse.quote(q) + '&from=' + fromLang + '&to=' + toLang + '&salt=' + str(
    salt) + '&sign=' + sign
    transList=''
    try:
        httpClient = http.client.HTTPConnection('api.fanyi.baidu.com')
        httpClient.request('GET', myurl)

        # response是HTTPResponse对象
        response = httpClient.getresponse()
        result_all = response.read().decode("utf-8")
        result = json.loads(result_all)
        trans_result=result['trans_result']
        for item in trans_result:
            transList+=item['dst']
        return transList
    except Exception as e:
        print (e)
    finally:
        if httpClient:
            httpClient.close()

# province list generate
#by GAO Han
def prov_ListArray():
    if(toLang=='en'):
        Top_text='Select from provinces below'
    else:
        Top_text=langTrans('Select from provinces below')
    default_action={'type':'postback','label':"default_label",'data':"default_data"}
    default_content={'type':'button',"style":"primary","height":"sm","margin":"xs"}
    prov_cont_array=[{"type": "text","text": Top_text}]
    if(toLang=='zh'):
        for item in root:
            name=item.get('provname')
            prov_item='prov_'+name
            default_action['label']=name
            default_action['data']=prov_item
            default_content['action']=default_action
            content_str=str(default_content)
            dict_temp=eval(content_str)
            prov_cont_array.append(dict_temp)
    else:
        for item in root:
            name=langTrans(item.get('provname')).capitalize()
            prov_item='prov_'+item.get('provname')
            default_action['label']=name
            default_action['data']=prov_item
            default_content['action']=default_action
            content_str=str(default_content)
            dict_temp=eval(content_str)
            prov_cont_array.append(dict_temp)
    return prov_cont_array

con=prov_ListArray()
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
            #display city list
            if(isinstance(event,PostbackEvent) and event.postback.data[0:5]=='prov_'):
                handle_CityList(event)
            #display hospital list
            elif(isinstance(event,PostbackEvent) and event.postback.data[0:5]=='city_'):
                handle_HospiList(event)
            #language switch
            elif(isinstance(event,PostbackEvent) and event.postback.data[0:7]=='langTo_'):
                curr_tolang=toLang
                lang_Switch(event)
                new_tolang=toLang
                if(curr_tolang!=new_tolang):
                    global con
                    #upgrade province list
                    con=prov_ListArray()
            else:
                continue
        else:
            if isinstance(event.message, TextMessage):
                # todo: 针对不同的文本输入进行不同的反应
                if(event.message.text.lower() in langTrans('hospitals')):
                    #display province list
                    handler_function3(event)
                if(event.message.text.lower() in langTrans('language')):
                    #display language list
                    lang_Choose(event)
                if(event.message.text.lower() in langTrans('news')):
                    #display virus news
                    handle_TextMessage(event)
                else:
                    #Q&A
                    QAEvent(event)

            if isinstance(event.message, LocationMessage):
                handle_LocationMessage(event)
            if isinstance(event.message, ImageMessage) or isinstance(event.message, VideoMessage) or isinstance(event.message, FileMessage) or isinstance(event.message, StickerMessage):
                #guidance
                handle_OtherMessage(event)

    return 'OK'

#by GAO Han -- generate language template
def langArray(dict):
    Top_text=langTrans('Select from languages below')
    lang_array=[{"type": "text","text": Top_text}]
    default_action={'type':'postback','label':"default_label",'data':"default_data"}
    default_content={'type':'button',"style":"link","height":"sm","margin":"xs"}
    for item in dict:
        if(toLang!='zh'):
            label_show=langTrans(dict[item])
        else:
            label_show=dict[item]
        langTo='langTo_'+item
        default_action['label']=label_show
        default_action['data']=langTo
        default_content['action']=default_action
        content_str=str(default_content)
        dict_temp=eval(content_str)
        lang_array.append(dict_temp)
    return lang_array

#by GAO Han -- provide user language choose message
def lang_Choose(event):
    array=langArray(lang_lib)
    line_bot_api.reply_message(
        event.reply_token,
        FlexSendMessage(
            alt_text="list",
            contents={
                "type": "bubble",
                "body": {
                "type": "box",
                "layout": "vertical",
                "contents":array
                }
            }
        )
    )

#by GAO Han -- language switch function
def lang_Switch(event):
    global toLang
    toLang=event.postback.data[7:]
    prompt=langTrans('修改成功！您当前使用的语言为'+lang_lib[toLang])
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=prompt)
    )
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
    bs = BeautifulSoup(webPage.text, 'html.parser')

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
    # 调用获取最新新闻的接口获取新闻
    hot_news = get_hotNews()
    label1=langTrans('View Detail')
    message = TemplateSendMessage(
        alt_text='Hot news about the coronavirus',
        template=CarouselTemplate(
            columns=[
                CarouselColumn(
                    thumbnail_image_url=str(hot_news[1][0],encoding='utf-8'),
                    title=str(hot_news[2][0],encoding='utf-8'),
                    text=str(hot_news[3][0],encoding='utf-8'),
                    actions=[
                        URIAction(uri=str(hot_news[0][0],encoding='utf-8'), label=label1)
                    ]
                ),
                CarouselColumn(
                    thumbnail_image_url=str(hot_news[1][1],encoding='utf-8'),
                    title=str(hot_news[2][1], encoding='utf-8'),
                    text=str(hot_news[3][1], encoding='utf-8'),
                    actions=[
                        URIAction(uri=str(hot_news[0][1], encoding='utf-8'), label=label1)
                    ]
                ),
                CarouselColumn(
                    thumbnail_image_url=str(hot_news[1][2], encoding='utf-8'),
                    title=str(hot_news[2][2], encoding='utf-8'),
                    text=str(hot_news[3][2], encoding='utf-8'),
                    actions=[
                        URIAction(uri=str(hot_news[0][2], encoding='utf-8'), label=label1)
                    ]
                ),
                CarouselColumn(
                    thumbnail_image_url=str(hot_news[1][3], encoding='utf-8'),
                    title=str(hot_news[2][3], encoding='utf-8'),
                    text=str(hot_news[3][3], encoding='utf-8'),
                    actions=[
                        URIAction(uri=str(hot_news[0][3], encoding='utf-8'), label=label1)
                    ]
                ),
                CarouselColumn(
                    thumbnail_image_url=str(hot_news[1][4], encoding='utf-8'),
                    title=str(hot_news[2][4], encoding='utf-8'),
                    text=str(hot_news[3][4], encoding='utf-8'),
                    actions=[
                        URIAction(uri=str(hot_news[0][4], encoding='utf-8'), label=label1)
                    ]
                )
            ]
        )
    )
    line_bot_api.reply_message(
        event.reply_token,
        message
    )


#by GAO Han -- language switch for Q&A part
def langVerseTrans(q):
    sign = appid + q + str(salt) + secretKey
    sign = hashlib.md5(sign.encode()).hexdigest()
    myurl = initurl + '?appid=' + appid + '&q=' + urllib.parse.quote(q) + '&from=' + toLang + '&to=en' + '&salt=' + str(
    salt) + '&sign=' + sign
    transList=''
    try:
        httpClient = http.client.HTTPConnection('api.fanyi.baidu.com')
        httpClient.request('GET', myurl)

        # response是HTTPResponse对象
        response = httpClient.getresponse()
        result_all = response.read().decode("utf-8")
        result = json.loads(result_all)
        trans_result=result['trans_result']
        for item in trans_result:
            transList+=item['dst']
        return transList
    except Exception as e:
        print (e)
    finally:
        if httpClient:
            httpClient.close()

def QAEvent(event):
    # createby: Zhang Mingxuan
    if toLang=='en':
        if event.message.text == 'Q&A':
            msg = 'You can ask quesiton like below:\nHow to do prevention?\nWhat should do outside?\nWhat to do if I have fever?\nCan I go to restaurant or bar?\nCan I go to park or mall?\nWhat should I do when I go back home?'\
            '\nWhat should I if I am out?\nI want to travel\nI want to have a trip\nI feel boring\nI am going mad\nI want to play or learn something\n'
        elif 'how' in event.message.text.lower() or 'prevention' in event.message.text.lower():
            msg = 'Wash hands '
        elif 'what' in event.message.text.lower() or 'outside' in event.message.text.lower():
            msg = 'Wearing a mask '
        elif 'have' in event.message.text.lower() or 'fever' in event.message.text.lower():
            msg = 'You should go to the hospital'
        elif 'restaurant' in event.message.text.lower() or 'bar' in event.message.text.lower():
            msg = 'NO! You should eat or drink at home! '
        elif 'park' in event.message.text.lower() or 'mall' in event.message.text.lower():
            msg = 'No! I said you should stay at home! '
        elif 'back' in event.message.text.lower() or 'home' in event.message.text.lower():
            msg = 'Remember to disinfect! '
        elif 'out' in event.message.text.lower():
            msg = 'Disinfect with alcohol-based hand rub! '
        elif 'travel' in event.message.text.lower() or 'trip' in event.message.text.lower():
            msg = 'How many times do I have to tell you not to go out! '
        elif 'boring' in event.message.text.lower() or 'mad' in event.message.text.lower():
            msg = 'You can take this opportunity to lose weight~ '
        elif 'play' in event.message.text.lower() or 'learn' in event.message.text.lower():
            msg = 'You can play games or learn how to cook. '
        else:
            msg = 'Sorry, for technical reasons, the service you requested is temporarily unavailable!\nPlease enter the ' \
                  'command as follow\n \'news\':view the latest news of coronavirus topic.' \
                  '\n \'Q&A\':start Q&A and get corresponding answers.' \
                  '\n \'hospital\':view the list of designated hospitals(Mainland China only).'\
                  '\n \'language\':change current language.'
    else:
        userMsg=langVerseTrans(event.message.text)
        if event.message.text == langTrans('Q&A'):
            msg = 'You can ask quesitons like:\nHow to do prevention?\nWhat should I do outside?\nWhat to do if I have fever?\nCan I go to restaurant or bar?\nCan I go to park or mall?\nWhat should I do when I go back home?'\
            '\nWhat should I do if I am out?\nI want to have a trip.\nI feel bored.\nI feel like I am going mad.\nI want to play or learn something.\n'
        elif 'how' in userMsg or 'prevention' in userMsg or 'prevent' in userMsg:
            msg = 'Wash hands'
        elif 'what' in userMsg or 'outside' in userMsg:
            msg = 'Wearing a mask'
        elif 'have' in userMsg or 'fever' in userMsg:
            msg = 'You should go to the hospital'
        elif 'restaurant' in userMsg or 'bar' in userMsg:
            msg = 'NO! You should eat or drink at home! '
        elif 'park' in userMsg or 'mall' in userMsg:
            msg = 'No! I said you should stay at home! '
        elif 'back' in userMsg or 'home' in userMsg:
            msg = 'Remember to disinfect! '
        elif 'out' in userMsg:
            msg = 'Disinfect with alcohol-based hand rub! '
        elif 'travel' in userMsg or 'trip' in userMsg:
            msg = 'How many times do I have to tell you not to go out! '
        elif 'boring' in userMsg or 'mad' in userMsg or 'crazy' in userMsg or 'bored' in userMsg:
            msg = 'You can take this opportunity to lose weight~ '
        elif 'play' in userMsg or 'learn' in userMsg:
            msg = 'You can play games or learn how to cook. '
        else:
            msg = 'Sorry, for technical reasons, the service you requested is temporarily unavailable!\nPlease enter the ' \
                  'command as follow\n \'news\' \tview the latest news of coronavirus topic.' \
                  '\n \'Q&A\' \tstart Q&A and get corresponding answers.' \
                  '\n \'hospital\' \t view the list of designated hospitals.(Mainland China only)'\
                  '\n \'language\' \t change current language.'\
                  '\n or send your location to get the distance to the nearest hospital and the time it takes to get there.'
        msg=langTrans(msg)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(msg)
    )

#by GAO Han -- generate city list based on given province
def city_ListArray(word,arr):
    if(toLang=='en'):
        Top_text='Select from cities below'
    else:
        Top_text=langTrans('Select from cities below')
    city_array=[{"type": "text","text": Top_text}]
    default_action={'type':'postback','label':"default_label",'data':"default_data"}
    default_content={'type':'button',"style":"secondary","height":"sm","margin":"xs"}
    for item in arr:
        city_data='city_'+item.get('cityname')+'OF'+word
        if(toLang=='zh'):
            default_action['label']= item.get('cityname')
        else:
            default_action['label']= langTrans(item.get('cityname')).capitalize()
        default_action['data']=city_data
        default_content['action']=default_action
        content_str=str(default_content)
        dict_temp=eval(content_str)
        city_array.append(dict_temp)
    return city_array

#Handle function3--display info about designated hospitals
#by GAO Han -- display all the provinces/municipality
def handler_function3(event):
    global con
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

#by GAO Han -- send city choose message to the user
def handle_CityList(event):
    for province in root:
        if (event.postback.data[5:].lower()==province.get('provname')):
            citylist=city_ListArray(province.get('provname'),province)
            break
        else:
            continue
    time.sleep(0.5)
    line_bot_api.reply_message(
        event.reply_token,
        FlexSendMessage(
            alt_text="list",
            contents={
                "type": "bubble",
                "body": {
                "type": "box",
                "layout": "vertical",
                "contents":citylist
                }
            }
        )
    )

#by GAO Han -- language tranform for hospital display part
def langTransform(q):
    sign = appid + q + str(salt) + secretKey
    sign = hashlib.md5(sign.encode()).hexdigest()
    myurl = initurl + '?appid=' + appid + '&q=' + urllib.parse.quote(q) + '&from=' + fromLang + '&to=' + toLang + '&salt=' + str(
    salt) + '&sign=' + sign
    transList=''
    try:
        httpClient = http.client.HTTPConnection('api.fanyi.baidu.com')
        httpClient.request('GET', myurl)

        # response是HTTPResponse对象
        response = httpClient.getresponse()
        result_all = response.read().decode("utf-8")
        result = json.loads(result_all)
        trans_result=result['trans_result']
        i=1
        for item in trans_result:
            transList+=str(i)+'. '+item['dst']+'\n'
            i+=1
        return transList
    except Exception as e:
        print (e)
    finally:
        if httpClient:
            httpClient.close()

#by GAO Han -- get hospital name based on given city and send to the user
def handle_HospiList(event):
    index=event.postback.data.find('OF')
    prov_str=event.postback.data[index+2:]
    hospitalList='';
    for province in root:
        if(province.get('provname')==prov_str):
            for city in province:
                if(city.get('cityname')==event.postback.data[5:index]):
                    for hospital in city:
                       hospitalList+=hospital.text+"\n"
                    if(toLang!='zh'):
                        hospitalList=langTransform(hospitalList)
                        str_list = list(hospitalList)
                        headStr=city.get('cityname')+'的定点医院名单'
                        insertStr=langTrans(headStr)
                        str_list.insert(0,insertStr+'\n')
                        hospitalList = ''.join(str_list)
                    else:
                        str_list=list(hospitalList)
                        str_list.insert(0,city.get('cityname')+'的定点医院有：\n')
                        hospitalList=''.join(str_list)
                    break
                else:
                    continue
            break
        else:
            continue
    time.sleep(0.5)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(hospitalList)
    )

#by ZHANG Mingxuan -- Google Map
def handle_LocationMessage(event):
    latdata = event.message.latitude
    latdata = str(latdata)
    lngdata = event.message.longitude
    lngdata = str(lngdata)
    '''
    destination_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input=Hospital&inputtype=textquery&fields=photos,formatted_address,name,rating,opening_hours,geometry&key=AIzaSyDjCjU2ntyjID5hgfFChltHAzI1y_9f96M"
    location_json = requests.get(destination_url)
    json_destination_formatted = json.loads(location_json.text)
    
    name = str(json_destination_formatted[u'candidates'][0][u'name'])
    destinaton_lat = str(json_destination_formatted[u'candidates'][0][u'geometry'][u'location'][u'lat'])
    destinaton_lng = str(json_destination_formatted[u'candidates'][0][u'geometry'][u'location'][u'lng'])
    '''
    hospital_location = "22.309060, 114.174662"
    key = "AIzaSyDjCjU2ntyjID5hgfFChltHAzI1y_9f96M"
    #requests_url = "https://maps.googleapis.com/maps/api/distancematrix/json?units=imperial&origins="+latdata+","+lngdata+"&destinations="+destinaton_lat+","+destinaton_lng+"&key=" + key
    requests_url = "https://maps.googleapis.com/maps/api/distancematrix/json?units=imperial&origins="+latdata+","+lngdata+"&destinations="+hospital_location+"&key=" + key
    distance_json = requests.get(requests_url)
    json_formatted = json.loads(distance_json.text)
    if(json_formatted[u'rows'][0][u'elements'][0][u'status']=='ZERO_RESULTS'):
        msg="Sorry,we cannot retrieve any results.Please try other locations."
    else:
        duration = json_formatted[u'rows'][0][u'elements'][0][u'duration'][u'text']
        distance = json_formatted[u'rows'][0][u'elements'][0][u'distance'][u'text']
        #route_infor = "The hospital is "+ name +". "+ "You are "+ distance + " away from your destination. It takes about " + duration + " to arrive there."
        route_infor = "You are "+ distance + " away from your destination. It takes about " + duration + " to arrive there."

        if(toLang=='en'):
            msg = str(route_infor)
        else:
            msg = langTrans(str(route_infor))
    if(toLang!='en'):
        msg = langTrans(msg)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(msg)
    )
# Handle function for guidance
def handle_OtherMessage(event):
    msg = 'Sorry, for technical reasons, the service you requested is temporarily unavailable!\nPlease enter the ' \
                  'command as follow\n \'news\' \tview the latest news of coronavirus topic' \
                  '\n \'Q&A\' \tstart Q&A and get corresponding answers' \
                  '\n \'hospital\' \t view the list of designated hospitals(Mainland China only)'\
                  '\n \'language\' \t change current language'\
                  '\n or send your location to get the distance to the nearest hospital and the time it takes to get there.'
    if(toLang!='en'):
        msg=langTrans(msg)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(msg)
    )


if __name__ == "__main__":
    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-d', '--debug', default=False, help='debug')
    options = arg_parser.parse_args()

    app.run(host='0.0.0.0', debug=options.debug, port=heroku_port)
